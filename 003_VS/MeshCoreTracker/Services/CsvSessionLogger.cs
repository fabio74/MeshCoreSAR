using Microsoft.Maui.Storage;
using System.Globalization;
using System.Text;
using MeshCoreTracker.Models;

namespace MeshCoreTracker.Services;

public sealed class CsvSessionLogger
{
    private readonly string _baseDirectory;
    private readonly Dictionary<string, string> _paths = new(StringComparer.Ordinal);
    private DateTimeOffset _sessionStarted = DateTimeOffset.Now;

    public CsvSessionLogger(string? baseDirectory = null)
    {
        _baseDirectory = baseDirectory ?? Path.Combine(FileSystem.AppDataDirectory, "data");
    }

    public void NewSession()
    {
        _sessionStarted = DateTimeOffset.Now;
        _paths.Clear();
    }

    public async Task<string> AppendAsync(TelemetryPoint point)
    {
        var path = PathFor(point.ContactName);
        var firstWrite = !File.Exists(path);
        await using var stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read);
        await using var writer = new StreamWriter(stream, new UTF8Encoding(false));

        if (firstWrite)
            await writer.WriteLineAsync("timestamp,contact,latitude,longitude,altitude_m,voltage_v,luminosity_lux,temperature_1_c,temperature_2_c,humidity_percent,barometer_hpa,lpp_hex");

        var t = point.Telemetry.TemperaturesC;
        var values = new[]
        {
            Csv(point.Timestamp.ToString("O", CultureInfo.InvariantCulture)),
            Csv(point.ContactName),
            F(point.Latitude, "0.000000"),
            F(point.Longitude, "0.000000"),
            F(point.AltitudeM, "0.00"),
            F(point.Telemetry.VoltageV, "0.00"),
            point.Telemetry.LuminosityLux?.ToString(CultureInfo.InvariantCulture) ?? "",
            t.Count > 0 ? F(t[0], "0.0") : "",
            t.Count > 1 ? F(t[1], "0.0") : "",
            F(point.Telemetry.HumidityPercent, "0.0"),
            F(point.Telemetry.BarometerHpa, "0.0"),
            point.LppHex
        };
        await writer.WriteLineAsync(string.Join(',', values));
        return path;
    }

    private string PathFor(string contactName)
    {
        if (_paths.TryGetValue(contactName, out var existing))
            return existing;

        var dayDirectory = Path.Combine(_baseDirectory, _sessionStarted.ToString("yyyy-MM-dd"));
        Directory.CreateDirectory(dayDirectory);
        var filename = $"{_sessionStarted:yyyy-MM-dd_HH-mm-ss}_{SafeName(contactName)}.csv";
        var path = Path.Combine(dayDirectory, filename);
        _paths[contactName] = path;
        return path;
    }

    private static string SafeName(string name)
    {
        foreach (var c in Path.GetInvalidFileNameChars())
            name = name.Replace(c, '_');
        return string.IsNullOrWhiteSpace(name) ? "contact" : name.Trim();
    }

    private static string Csv(string value)
    {
        return "\"" + value.Replace("\"", "\"\"") + "\"";
    }
    private static string F(double value, string format) => value.ToString(format, CultureInfo.InvariantCulture);
    private static string F(double? value, string format) => value?.ToString(format, CultureInfo.InvariantCulture) ?? "";
}
