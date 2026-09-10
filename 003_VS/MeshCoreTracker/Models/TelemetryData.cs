namespace MeshCoreTracker.Models;

public sealed class TelemetryData
{
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public double? AltitudeM { get; set; }
    public double? VoltageV { get; set; }
    public int? LuminosityLux { get; set; }
    public List<double> TemperaturesC { get; } = [];
    public double? HumidityPercent { get; set; }
    public double? BarometerHpa { get; set; }
    public List<string> Unknown { get; } = [];

    public bool HasGps => Latitude.HasValue && Longitude.HasValue;
}
