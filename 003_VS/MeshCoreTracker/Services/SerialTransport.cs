using System.IO.Ports;
using MeshCoreTracker.MeshCore;

namespace MeshCoreTracker.Services;

public sealed class SerialTransport : IAsyncDisposable
{
    private SerialPort? _port;
    private CancellationTokenSource? _readCts;
    private Task? _readTask;
    private readonly UsbFrameParser _parser = new();
    private readonly SemaphoreSlim _writeLock = new(1, 1);

    public event Action<byte[]>? FrameReceived;
    public event Action<string>? Error;
    public event Action<string>? Log;

    public bool IsConnected => _port?.IsOpen == true;

    public static string[] GetPortNames() => SerialPort.GetPortNames()
        .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
        .ToArray();

    public Task ConnectAsync(string portName, int baudRate = 115200)
    {
        if (IsConnected)
            return Task.CompletedTask;

        var port = new SerialPort(portName, baudRate)
        {
            ReadTimeout = 500,
            WriteTimeout = 1000,
            DtrEnable = true,
            RtsEnable = true
        };

        port.Open();
        try { port.DiscardInBuffer(); } catch { }

        _port = port;
        _readCts = new CancellationTokenSource();
        _readTask = Task.Run(() => ReadLoopAsync(_readCts.Token));
        return Task.CompletedTask;
    }

    public async Task SendAsync(byte[] payload, CancellationToken cancellationToken = default)
    {
        var port = _port;
        if (port?.IsOpen != true)
            throw new InvalidOperationException("Porta seriale non connessa.");

        var packet = MeshCoreProtocol.EncodeUsbFrame(payload);
        await _writeLock.WaitAsync(cancellationToken);
        try
        {
            await port.BaseStream.WriteAsync(packet, cancellationToken);
            await port.BaseStream.FlushAsync(cancellationToken);
            Log?.Invoke($"TX {Convert.ToHexString(payload)}");
        }
        finally
        {
            _writeLock.Release();
        }
    }

    private async Task ReadLoopAsync(CancellationToken cancellationToken)
    {
        var buffer = new byte[4096];
        try
        {
            while (!cancellationToken.IsCancellationRequested && _port?.IsOpen == true)
            {
                var count = await _port.BaseStream.ReadAsync(buffer, cancellationToken);
                if (count <= 0)
                    continue;

                foreach (var frame in _parser.Feed(buffer.AsSpan(0, count)))
                {
                    Log?.Invoke($"RX {Convert.ToHexString(frame)}");
                    FrameReceived?.Invoke(frame);
                }
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            if (!cancellationToken.IsCancellationRequested)
                Error?.Invoke(ex.Message);
        }
    }

    public async Task DisconnectAsync()
    {
        var cts = _readCts;
        _readCts = null;
        if (cts is not null)
        {
            cts.Cancel();
            cts.Dispose();
        }

        var port = _port;
        _port = null;
        if (port is not null)
        {
            try { port.Close(); } catch { }
            port.Dispose();
        }

        if (_readTask is not null)
        {
            try { await _readTask.WaitAsync(TimeSpan.FromSeconds(1)); } catch { }
            _readTask = null;
        }
    }

    public async ValueTask DisposeAsync()
    {
        await DisconnectAsync();
        _writeLock.Dispose();
    }
}
