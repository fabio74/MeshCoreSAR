using System.Buffers.Binary;
using MeshCoreTracker.Models;

namespace MeshCoreTracker.MeshCore;

public static class CayenneLppDecoder
{
    private static readonly Dictionary<byte, int> Lengths = new()
    {
        [0x00] = 1,
        [0x01] = 1,
        [0x02] = 2,
        [0x03] = 2,
        [0x65] = 2,
        [0x66] = 1,
        [0x67] = 2,
        [0x68] = 1,
        [0x71] = 6,
        [0x73] = 2,
        [0x74] = 2,
        [0x86] = 6,
        [0x88] = 9,
    };

    public static TelemetryData Decode(ReadOnlySpan<byte> payload)
    {
        var result = new TelemetryData();
        var i = 0;

        while (i + 2 <= payload.Length)
        {
            var channel = payload[i++];
            var type = payload[i++];

            if (!Lengths.TryGetValue(type, out var length) || i + length > payload.Length)
            {
                result.Unknown.Add($"ch={channel} type=0x{type:X2} data={Convert.ToHexString(payload[i..])}");
                break;
            }

            var raw = payload.Slice(i, length);
            i += length;

            switch (type)
            {
                case 0x88 when raw.Length == 9:
                    result.Latitude = ReadInt24BigEndian(raw[..3]) / 10000.0;
                    result.Longitude = ReadInt24BigEndian(raw.Slice(3, 3)) / 10000.0;
                    result.AltitudeM = ReadInt24BigEndian(raw.Slice(6, 3)) / 100.0;
                    break;

                case 0x74:
                    result.VoltageV = BinaryPrimitives.ReadUInt16BigEndian(raw) / 100.0;
                    break;

                case 0x65:
                    result.LuminosityLux = BinaryPrimitives.ReadUInt16BigEndian(raw);
                    break;

                case 0x67:
                    result.TemperaturesC.Add(BinaryPrimitives.ReadInt16BigEndian(raw) / 10.0);
                    break;

                case 0x68:
                    result.HumidityPercent = raw[0] / 2.0;
                    break;

                case 0x73:
                    result.BarometerHpa = BinaryPrimitives.ReadUInt16BigEndian(raw) / 10.0;
                    break;
            }
        }

        return result;
    }

    private static int ReadInt24BigEndian(ReadOnlySpan<byte> raw)
    {
        var value = (raw[0] << 16) | (raw[1] << 8) | raw[2];
        if ((value & 0x800000) != 0)
            value -= 1 << 24;
        return value;
    }
}
