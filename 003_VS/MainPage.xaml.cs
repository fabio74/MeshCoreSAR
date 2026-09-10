using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Microsoft.Maui.ApplicationModel;
using Microsoft.Maui.ApplicationModel.DataTransfer;
using Microsoft.Maui.Storage;
using MeshCoreTracker.MeshCore;
using MeshCoreTracker.Models;
using MeshCoreTracker.Services;

namespace MeshCoreTracker;

public partial class MainPage : ContentPage
{
    private readonly SerialTransport _serial = new();
    private readonly CsvSessionLogger _csv = new();
    private readonly Dictionary<string, MeshContact> _contacts = new(StringComparer.Ordinal);
    private readonly Dictionary<string, CheckBox> _pollChecks = new(StringComparer.Ordinal);
    private readonly Dictionary<string, CheckBox> _mapChecks = new(StringComparer.Ordinal);
    private readonly Dictionary<string, List<TrackPoint>> _tracks = new(StringComparer.Ordinal);
    private readonly Dictionary<string, TelemetryPoint> _latest = new(StringComparer.Ordinal);

    private CancellationTokenSource? _pollCts;
    private MeshContact? _currentPollContact;
    private TaskCompletionSource<SentResponse>? _sentTcs;
    private TaskCompletionSource<TelemetryResponse>? _telemetryTcs;
    private TaskCompletionSource<int>? _errorTcs;
    private bool _mapReady;

    public MainPage()
    {
        InitializeComponent();
        _serial.FrameReceived += frame => MainThread.BeginInvokeOnMainThread(() => _ = HandleFrameAsync(frame));
        _serial.Error += message => MainThread.BeginInvokeOnMainThread(() =>
        {
            SetStatus($"Errore seriale: {message}");
            UsbStatusLabel.Text = "Errore seriale";
        });
        MapProviderPicker.SelectedIndex = 0;
        RefreshPorts();
    }

    protected override void OnAppearing()
    {
        base.OnAppearing();
        RefreshPorts();
    }

    private void RefreshPorts()
    {
        var previous = PortPicker.SelectedItem as string;
        var ports = SerialTransport.GetPortNames();
        PortPicker.ItemsSource = ports;
        if (ports.Length == 0)
        {
            PortPicker.SelectedIndex = -1;
            SetStatus("Nessuna porta seriale rilevata.");
            return;
        }

        var index = previous is null ? -1 : Array.IndexOf(ports, previous);
        PortPicker.SelectedIndex = index >= 0 ? index : 0;
    }

    private void OnRefreshPortsClicked(object sender, EventArgs e) => RefreshPorts();

    private async void OnConnectClicked(object sender, EventArgs e)
    {
        if (PortPicker.SelectedItem is not string portName || string.IsNullOrWhiteSpace(portName))
        {
            await DisplayAlert("MeshCore", "Selezionare una porta seriale.", "OK");
            return;
        }

        try
        {
            await _serial.ConnectAsync(portName, 115200);
            UsbStatusLabel.Text = $"Connesso: {portName}";
            ConnectButton.IsEnabled = false;
            DisconnectButton.IsEnabled = true;
            SetStatus("USB connessa. Inizializzazione MeshCore…");
            await _serial.SendAsync(MeshCoreProtocol.BuildAppStart());
        }
        catch (Exception ex)
        {
            SetStatus($"Connessione fallita: {ex.Message}");
            await DisplayAlert("Errore seriale", ex.Message, "OK");
        }
    }

    private async void OnDisconnectClicked(object sender, EventArgs e)
    {
        StopPolling();
        await _serial.DisconnectAsync();
        UsbStatusLabel.Text = "Non connesso";
        ConnectButton.IsEnabled = true;
        DisconnectButton.IsEnabled = false;
        SetStatus("USB disconnessa.");
    }

    private async Task HandleFrameAsync(byte[] frame)
    {
        if (frame.Length == 0)
            return;

        try
        {
            switch (frame[0])
            {
                case MeshCoreProtocol.RespSelfInfo:
                    await _serial.SendAsync(MeshCoreProtocol.BuildDeviceQuery());
                    var epoch = (uint)DateTimeOffset.UtcNow.ToUnixTimeSeconds();
                    await _serial.SendAsync(MeshCoreProtocol.BuildSetDeviceTime(epoch));
                    await _serial.SendAsync(MeshCoreProtocol.BuildGetContacts());
                    SetStatus("MeshCore inizializzato. Lettura contatti…");
                    break;

                case MeshCoreProtocol.RespContactsStart:
                    _contacts.Clear();
                    _pollChecks.Clear();
                    _mapChecks.Clear();
                    ContactsPanel.Children.Clear();
                    TracksPanel.Children.Clear();
                    break;

                case MeshCoreProtocol.RespContact:
                    AddContact(MeshCoreProtocol.DecodeContact(frame));
                    break;

                case MeshCoreProtocol.RespEndOfContacts:
                    SetStatus($"Contatti caricati: {_contacts.Count}");
                    break;

                case MeshCoreProtocol.RespSent:
                    _sentTcs?.TrySetResult(MeshCoreProtocol.DecodeSentResponse(frame));
                    break;

                case MeshCoreProtocol.RespError:
                    _errorTcs?.TrySetResult(frame.Length > 1 ? frame[1] : -1);
                    break;

                case MeshCoreProtocol.PushTelemetryResponse:
                    var response = MeshCoreProtocol.DecodeTelemetryResponse(frame);
                    await ProcessTelemetryAsync(response);
                    if (_currentPollContact is not null && PrefixEquals(_currentPollContact.Prefix, response.PublicKeyPrefix))
                        _telemetryTcs?.TrySetResult(response);
                    break;
            }
        }
        catch (Exception ex)
        {
            SetStatus($"Errore frame 0x{frame[0]:X2}: {ex.Message}");
        }
    }

    private void AddContact(MeshContact contact)
    {
        _contacts[contact.KeyHex] = contact;

        var pollCheck = new CheckBox { IsChecked = false };
        var pollLabel = new Label { Text = contact.Name, VerticalOptions = LayoutOptions.Center, TextColor = Color.FromArgb("#111827") };
        var pollRow = new HorizontalStackLayout { Spacing = 6 };
        pollRow.Children.Add(pollCheck);
        pollRow.Children.Add(pollLabel);
        ContactsPanel.Children.Add(pollRow);
        _pollChecks[contact.KeyHex] = pollCheck;

        var mapCheck = new CheckBox { IsChecked = true };
        var mapLabel = new Label { Text = contact.Name, VerticalOptions = LayoutOptions.Center, TextColor = Color.FromArgb("#111827") };
        var mapRow = new HorizontalStackLayout { Spacing = 6 };
        mapRow.Children.Add(mapCheck);
        mapRow.Children.Add(mapLabel);
        TracksPanel.Children.Add(mapRow);
        _mapChecks[contact.KeyHex] = mapCheck;

        mapCheck.CheckedChanged += async (_, e) =>
        {
            await SetMapTrackVisibilityAsync(contact.Name, e.Value);
        };
    }

    private async void OnStartClicked(object sender, EventArgs e)
    {
        if (!_serial.IsConnected)
        {
            await DisplayAlert("Polling", "Connettere prima il dispositivo MeshCore USB.", "OK");
            return;
        }

        if (GetSelectedContacts().Count == 0)
        {
            await DisplayAlert("Polling", "Selezionare almeno un contatto.", "OK");
            return;
        }

        var intPing = GetIntPingSeconds();
        IntPingEntry.Text = intPing.ToString(CultureInfo.InvariantCulture);
        _csv.NewSession();
        _pollCts = new CancellationTokenSource();
        StartButton.IsEnabled = false;
        StopButton.IsEnabled = true;
        IntPingEntry.IsEnabled = false;
        _ = PollingLoopAsync(_pollCts.Token);
    }

    private void OnStopClicked(object sender, EventArgs e) => StopPolling();

    private void StopPolling()
    {
        _pollCts?.Cancel();
        _pollCts?.Dispose();
        _pollCts = null;
        _currentPollContact = null;
        _sentTcs?.TrySetCanceled();
        _telemetryTcs?.TrySetCanceled();
        _errorTcs?.TrySetCanceled();
        StartButton.IsEnabled = true;
        StopButton.IsEnabled = false;
        IntPingEntry.IsEnabled = true;
    }

    private async Task PollingLoopAsync(CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var cycleStart = Stopwatch.GetTimestamp();
                var selected = await MainThread.InvokeOnMainThreadAsync(GetSelectedContacts);
                if (selected.Count == 0)
                {
                    await MainThread.InvokeOnMainThreadAsync(StopPolling);
                    return;
                }

                var intPingSeconds = await MainThread.InvokeOnMainThreadAsync(GetIntPingSeconds);
                await SetStatusAsync($"Nuovo ciclo: {selected.Count} contatti — IntPing {intPingSeconds} s");

                foreach (var contact in selected)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    await PollContactAsync(contact, cancellationToken);
                    await Task.Delay(300, cancellationToken);
                }

                _currentPollContact = null;
                var elapsed = Stopwatch.GetElapsedTime(cycleStart);
                var target = TimeSpan.FromSeconds(intPingSeconds);
                var delay = target - elapsed;
                if (delay < TimeSpan.FromMilliseconds(250))
                    delay = TimeSpan.FromMilliseconds(250);

                await SetStatusAsync($"Ciclo completato. Prossimo ciclo tra {delay.TotalSeconds:0.0} s");
                await Task.Delay(delay, cancellationToken);
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            await SetStatusAsync($"Polling interrotto: {ex.Message}");
            await MainThread.InvokeOnMainThreadAsync(StopPolling);
        }
    }

    private async Task PollContactAsync(MeshContact contact, CancellationToken cancellationToken)
    {
        _currentPollContact = contact;

        for (var attempt = 0; attempt < 2; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            _sentTcs = NewTcs<SentResponse>();
            _telemetryTcs = NewTcs<TelemetryResponse>();
            _errorTcs = NewTcs<int>();

            await SetStatusAsync($"Richiesta posizione → {contact.Name}{(attempt == 0 ? "" : " — retry 1")}");
            await _serial.SendAsync(MeshCoreProtocol.BuildTelemetryRequest(contact.PublicKey), cancellationToken);

            var sentOutcome = await WaitForSentOrErrorAsync(TimeSpan.FromMilliseconds(2500), cancellationToken);
            if (sentOutcome.ErrorCode.HasValue)
            {
                if (attempt == 0)
                {
                    await SetStatusAsync($"{contact.Name}: MeshCore ERR {sentOutcome.ErrorCode}; nuovo tentativo…");
                    await Task.Delay(1000, cancellationToken);
                    continue;
                }

                await SetStatusAsync($"{contact.Name}: MeshCore ERR {sentOutcome.ErrorCode} dopo retry; passo al successivo");
                return;
            }

            if (sentOutcome.Sent is null)
            {
                if (attempt == 0)
                {
                    await SetStatusAsync($"{contact.Name}: timeout RESP_CODE_SENT; nuovo tentativo…");
                    await Task.Delay(750, cancellationToken);
                    continue;
                }

                await SetStatusAsync($"{contact.Name}: nessuna risposta dopo 2 tentativi; passo al successivo");
                return;
            }

            var waitMs = Math.Clamp((long)sentOutcome.Sent.SuggestedTimeoutMs + 1500L, 2500L, 60000L);
            await SetStatusAsync($"{contact.Name}: richiesta inviata, attesa max {waitMs / 1000.0:0.0} s");

            var telemOutcome = await WaitForTelemetryOrErrorAsync(TimeSpan.FromMilliseconds(waitMs), cancellationToken);
            if (telemOutcome.Telemetry is not null)
            {
                if (telemOutcome.Telemetry.Decoded.HasGps)
                    await SetStatusAsync($"{contact.Name}: {telemOutcome.Telemetry.Decoded.Latitude:0.000000}, {telemOutcome.Telemetry.Decoded.Longitude:0.000000}");
                else
                    await SetStatusAsync($"{contact.Name}: telemetria ricevuta senza GPS");
                return;
            }

            if (attempt == 0)
            {
                await SetStatusAsync(telemOutcome.ErrorCode.HasValue
                    ? $"{contact.Name}: MeshCore ERR {telemOutcome.ErrorCode}; nuovo tentativo…"
                    : $"{contact.Name}: timeout telemetria; nuovo tentativo…");
                await Task.Delay(750, cancellationToken);
                continue;
            }

            await SetStatusAsync($"{contact.Name}: nessuna telemetria dopo 2 tentativi; passo al successivo");
            return;
        }
    }

    private async Task<(SentResponse? Sent, int? ErrorCode)> WaitForSentOrErrorAsync(TimeSpan timeout, CancellationToken ct)
    {
        var timeoutTask = Task.Delay(timeout, ct);
        var completed = await Task.WhenAny(_sentTcs!.Task, _errorTcs!.Task, timeoutTask);
        if (completed == _sentTcs.Task)
            return (await _sentTcs.Task, null);
        if (completed == _errorTcs.Task)
            return (null, await _errorTcs.Task);
        ct.ThrowIfCancellationRequested();
        return (null, null);
    }

    private async Task<(TelemetryResponse? Telemetry, int? ErrorCode)> WaitForTelemetryOrErrorAsync(TimeSpan timeout, CancellationToken ct)
    {
        var timeoutTask = Task.Delay(timeout, ct);
        var completed = await Task.WhenAny(_telemetryTcs!.Task, _errorTcs!.Task, timeoutTask);
        if (completed == _telemetryTcs.Task)
            return (await _telemetryTcs.Task, null);
        if (completed == _errorTcs.Task)
            return (null, await _errorTcs.Task);
        ct.ThrowIfCancellationRequested();
        return (null, null);
    }

    private async Task ProcessTelemetryAsync(TelemetryResponse response)
    {
        var contact = FindContactByPrefix(response.PublicKeyPrefix);
        if (contact is null)
        {
            SetStatus($"0x8B da contatto sconosciuto: {Convert.ToHexString(response.PublicKeyPrefix)}");
            return;
        }

        var gps = response.Decoded;
        if (!gps.HasGps)
            return;

        var now = DateTimeOffset.Now;
        var point = new TelemetryPoint(
            now,
            contact.Name,
            gps.Latitude!.Value,
            gps.Longitude!.Value,
            gps.AltitudeM,
            gps,
            Convert.ToHexString(response.LppPayload).ToLowerInvariant());

        if (!_tracks.TryGetValue(contact.Name, out var track))
        {
            track = [];
            _tracks[contact.Name] = track;
        }
        track.Add(new TrackPoint(point.Latitude, point.Longitude, point.AltitudeM, now));
        _latest[contact.Name] = point;

        await RenderTrackAsync(contact);
        UpdateCoordinatesStatus();
        var path = await _csv.AppendAsync(point);
        SetStatus($"{contact.Name}: {point.Latitude:0.000000}, {point.Longitude:0.000000} — CSV {Path.GetFileName(path)}");
    }

    private MeshContact? FindContactByPrefix(byte[] prefix) =>
        _contacts.Values.FirstOrDefault(c => PrefixEquals(c.Prefix, prefix));

    private static bool PrefixEquals(byte[] a, byte[] b) => a.AsSpan().SequenceEqual(b);

    private List<MeshContact> GetSelectedContacts() =>
        _contacts.Values
            .Where(c => _pollChecks.TryGetValue(c.KeyHex, out var box) && box.IsChecked)
            .ToList();

    private int GetIntPingSeconds()
    {
        if (!int.TryParse(IntPingEntry.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var seconds))
            seconds = 15;
        return Math.Clamp(seconds, 5, 3600);
    }

    private async Task RenderTrackAsync(MeshContact contact)
    {
        if (!_mapReady || !_tracks.TryGetValue(contact.Name, out var points))
            return;

        var visible = _mapChecks.TryGetValue(contact.KeyHex, out var check) && check.IsChecked;
        var dto = points.Select(p => new
        {
            lat = p.Lat,
            lon = p.Lon,
            alt = p.Alt,
            time = p.Timestamp.ToString("HH:mm:ss"),
            timestamp = p.Timestamp.ToString("O")
        });

        var nameJson = JsonSerializer.Serialize(contact.Name);
        var pointsJson = JsonSerializer.Serialize(dto);
        var visibleJson = visible ? "true" : "false";
        await MapWebView.EvaluateJavaScriptAsync($"upsertTrack({nameJson},{pointsJson},{visibleJson});");
    }

    private async Task SetMapTrackVisibilityAsync(string name, bool visible)
    {
        if (!_mapReady)
            return;
        await MapWebView.EvaluateJavaScriptAsync($"setTrackVisible({JsonSerializer.Serialize(name)},{(visible ? "true" : "false")});");
    }

    private void UpdateCoordinatesStatus()
    {
        if (_latest.Count == 0)
        {
            CoordinatesLabel.Text = "Coordinate dispositivi: —";
            return;
        }

        CoordinatesLabel.Text = "Coordinate dispositivi: " + string.Join("  |  ",
            _latest.OrderBy(x => x.Key, StringComparer.OrdinalIgnoreCase)
                .Select(x => $"{x.Key}: {x.Value.Latitude:0.000000}, {x.Value.Longitude:0.000000}"));
    }

    private async void OnMapNavigated(object sender, WebNavigatedEventArgs e)
    {
        if (e.Result != WebNavigationResult.Success)
            return;
        _mapReady = true;
        await SetMapProviderAsync(MapProviderPicker.SelectedIndex);
        foreach (var contact in _contacts.Values)
            await RenderTrackAsync(contact);
    }

    private async void OnMapProviderChanged(object sender, EventArgs e)
    {
        if (_mapReady)
            await SetMapProviderAsync(MapProviderPicker.SelectedIndex);
    }

    private async Task SetMapProviderAsync(int index)
    {
        var provider = index switch { 1 => "topo", 2 => "esri", _ => "osm" };
        await MapWebView.EvaluateJavaScriptAsync($"setBaseLayer('{provider}');");
    }

    private async void OnFitTracksClicked(object sender, EventArgs e)
    {
        if (_mapReady)
            await MapWebView.EvaluateJavaScriptAsync("fitVisibleTracks();");
    }

    private async void OnLoadGeoTiffClicked(object sender, EventArgs e)
    {
        try
        {
            var file = await FilePicker.Default.PickAsync(new PickOptions { PickerTitle = "Seleziona GeoTIFF (.tif/.tiff)" });
            if (file is null)
                return;
            var extension = Path.GetExtension(file.FileName);
            if (!extension.Equals(".tif", StringComparison.OrdinalIgnoreCase) &&
                !extension.Equals(".tiff", StringComparison.OrdinalIgnoreCase))
            {
                await DisplayAlert("GeoTIFF", "Selezionare un file .tif o .tiff.", "OK");
                return;
            }

            SetStatus($"Caricamento GeoTIFF {file.FileName}…");
            await using var stream = await file.OpenReadAsync();
            using var ms = new MemoryStream();
            await stream.CopyToAsync(ms);
            var base64 = Convert.ToBase64String(ms.ToArray());

            // Chunked transfer avoids one huge EvaluateJavaScriptAsync command.
            await MapWebView.EvaluateJavaScriptAsync($"beginGeoTiffUpload({JsonSerializer.Serialize(file.FileName)});");
            const int chunkSize = 240_000;
            for (var i = 0; i < base64.Length; i += chunkSize)
            {
                var chunk = base64.Substring(i, Math.Min(chunkSize, base64.Length - i));
                await MapWebView.EvaluateJavaScriptAsync($"appendGeoTiffChunk({JsonSerializer.Serialize(chunk)});");
            }
            await MapWebView.EvaluateJavaScriptAsync("finishGeoTiffUpload();");
            SetStatus("GeoTIFF: elaborazione raster…");
            for (var attempt = 0; attempt < 120; attempt++)
            {
                await Task.Delay(250);
                var result = await MapWebView.EvaluateJavaScriptAsync("getGeoTiffStatus();");
                result = result?.Trim().Trim('"') ?? "";
                if (result.StartsWith("OK ", StringComparison.Ordinal))
                {
                    SetStatus($"GeoTIFF: {result}");
                    break;
                }
                if (result.StartsWith("ERROR ", StringComparison.Ordinal))
                    throw new InvalidOperationException(result[6..]);
            }
        }
        catch (Exception ex)
        {
            await DisplayAlert("GeoTIFF", ex.Message, "OK");
            SetStatus($"Errore GeoTIFF: {ex.Message}");
        }
    }

    private async void OnExportGpxClicked(object sender, EventArgs e)
    {
        if (_tracks.Values.All(x => x.Count == 0))
        {
            await DisplayAlert("GPX", "Non ci sono tracce da esportare.", "OK");
            return;
        }

        try
        {
            var path = GpxExporter.Export(_tracks);
            SetStatus($"GPX creato: {path}");
            await Share.Default.RequestAsync(new ShareFileRequest
            {
                Title = "Esporta tracce MeshCore GPX",
                File = new ShareFile(path, "application/gpx+xml")
            });
        }
        catch (Exception ex)
        {
            await DisplayAlert("GPX", ex.Message, "OK");
        }
    }

    private void OnSelectAllPollClicked(object sender, EventArgs e)
    {
        foreach (var box in _pollChecks.Values) box.IsChecked = true;
    }

    private void OnSelectNonePollClicked(object sender, EventArgs e)
    {
        foreach (var box in _pollChecks.Values) box.IsChecked = false;
    }

    private void OnShowAllTracksClicked(object sender, EventArgs e)
    {
        foreach (var box in _mapChecks.Values) box.IsChecked = true;
    }

    private void OnHideAllTracksClicked(object sender, EventArgs e)
    {
        foreach (var box in _mapChecks.Values) box.IsChecked = false;
    }

    private void SetStatus(string message) => OperationStatusLabel.Text = message;
    private Task SetStatusAsync(string message) => MainThread.InvokeOnMainThreadAsync(() => SetStatus(message));

    private static TaskCompletionSource<T> NewTcs<T>() =>
        new(TaskCreationOptions.RunContinuationsAsynchronously);
}
