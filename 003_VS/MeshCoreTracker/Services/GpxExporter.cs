using Microsoft.Maui.Storage;
using System.Globalization;
using System.Xml.Linq;
using MeshCoreTracker.Models;

namespace MeshCoreTracker.Services;

public static class GpxExporter
{
    public static string Export(IReadOnlyDictionary<string, List<TrackPoint>> tracks, string? outputPath = null)
    {
        var exportDir = Path.Combine(FileSystem.AppDataDirectory, "exports");
        Directory.CreateDirectory(exportDir);
        outputPath ??= Path.Combine(exportDir, $"MeshCoreTracks_{DateTime.Now:yyyy-MM-dd_HH-mm-ss}.gpx");

        XNamespace ns = "http://www.topografix.com/GPX/1/1";
        XNamespace xsi = "http://www.w3.org/2001/XMLSchema-instance";

        var gpx = new XElement(ns + "gpx",
            new XAttribute("version", "1.1"),
            new XAttribute("creator", "MeshCore Tracker"),
            new XAttribute(XNamespace.Xmlns + "xsi", xsi),
            new XAttribute(xsi + "schemaLocation", "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"),
            new XElement(ns + "metadata",
                new XElement(ns + "name", "MeshCore Tracker"),
                new XElement(ns + "time", DateTimeOffset.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture))));

        foreach (var (name, points) in tracks.OrderBy(x => x.Key, StringComparer.OrdinalIgnoreCase))
        {
            if (points.Count == 0)
                continue;

            var segment = new XElement(ns + "trkseg");
            foreach (var p in points)
            {
                var trkpt = new XElement(ns + "trkpt",
                    new XAttribute("lat", p.Lat.ToString("0.00000000", CultureInfo.InvariantCulture)),
                    new XAttribute("lon", p.Lon.ToString("0.00000000", CultureInfo.InvariantCulture)));
                if (p.Alt.HasValue)
                    trkpt.Add(new XElement(ns + "ele", p.Alt.Value.ToString("0.00", CultureInfo.InvariantCulture)));
                trkpt.Add(new XElement(ns + "time", p.Timestamp.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture)));
                segment.Add(trkpt);
            }

            gpx.Add(new XElement(ns + "trk",
                new XElement(ns + "name", name),
                segment));
        }

        new XDocument(new XDeclaration("1.0", "utf-8", null), gpx).Save(outputPath);
        return outputPath;
    }
}
