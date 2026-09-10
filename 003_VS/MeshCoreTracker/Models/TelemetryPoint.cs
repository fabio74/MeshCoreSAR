namespace MeshCoreTracker.Models;

public sealed record TelemetryPoint(
    DateTimeOffset Timestamp,
    string ContactName,
    double Latitude,
    double Longitude,
    double? AltitudeM,
    TelemetryData Telemetry,
    string LppHex);
