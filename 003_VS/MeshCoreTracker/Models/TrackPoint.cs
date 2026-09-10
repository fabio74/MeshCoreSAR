namespace MeshCoreTracker.Models;

public sealed record TrackPoint(
    double Lat,
    double Lon,
    double? Alt,
    DateTimeOffset Timestamp);
