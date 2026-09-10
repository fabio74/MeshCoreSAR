using System.Buffers.Binary;
using System.Text;
using MeshCoreTracker.Models;

namespace MeshCoreTracker.MeshCore;

public static class MeshCoreProtocol
{
    public const byte CmdAppStart = 0x01;
    public const byte CmdGetContacts = 0x04;
    public const byte CmdSetDeviceTime = 0x06;
    public const byte CmdDeviceQuery = 0x16;
    public const byte CmdSendTelemetryReq = 0x27;

    public const byte RespError = 0x01;
    public const byte RespContactsStart = 0x02;
    public const byte RespContact = 0x03;
    public const byte RespEndOfContacts = 0x04;
    public const byte RespSelfInfo = 0x05;
    public const byte RespSent = 0x06;
    public const byte RespDeviceInfo = 0x0D;
    public const byte PushTelemetryResponse = 0x8B;

    public static byte[] BuildAppStart(string appName = "MeshCoreTracker", byte protocolVersion = 3)
    {
        var name = Encoding.UTF8.GetBytes(appName);
        var result = new byte[8 + name.Length];
        result[0] = CmdAppStart;
        result[1] = protocolVersion;
        // bytes 2..7 reserved = 0
        Buffer.BlockCopy(name, 0, result, 8, name.Length);
        return result;
    }

    public static byte[] BuildDeviceQuery(byte protocolVersion = 3) => [CmdDeviceQuery, protocolVersion];

    public static byte[] BuildSetDeviceTime(uint epochSeconds)
    {
        var result = new byte[5];
        result[0] = CmdSetDeviceTime;
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(1), epochSeconds);
        return result;
    }

    public static byte[] BuildGetContacts() => [CmdGetContacts];

    public static byte[] BuildTelemetryRequest(byte[] publicKey)
    {
        if (publicKey.Length != 32)
            throw new ArgumentException("La public key MeshCore deve essere di 32 byte.", nameof(publicKey));

        var result = new byte[36];
        result[0] = CmdSendTelemetryReq;
        // bytes 1..3 reserved = 0
        Buffer.BlockCopy(publicKey, 0, result, 4, 32);
        return result;
    }

    public static byte[] EncodeUsbFrame(byte[] payload)
    {
        if (payload.Length > ushort.MaxValue)
            throw new ArgumentOutOfRangeException(nameof(payload));

        var packet = new byte[payload.Length + 3];
        packet[0] = (byte)'<';
        BinaryPrimitives.WriteUInt16LittleEndian(packet.AsSpan(1, 2), (ushort)payload.Length);
        Buffer.BlockCopy(payload, 0, packet, 3, payload.Length);
        return packet;
    }

    public static MeshContact DecodeContact(byte[] frame)
    {
        if (frame.Length < 148 || frame[0] != RespContact)
            throw new InvalidDataException($"RESP_CODE_CONTACT non valida ({frame.Length} byte)." );

        var publicKey = frame.AsSpan(1, 32).ToArray();
        var advType = frame[33];
        var flags = frame[34];
        var outPathLength = unchecked((sbyte)frame[35]);
        var name = DecodeCString(frame.AsSpan(100, 32));
        var lastAdvert = BinaryPrimitives.ReadUInt32LittleEndian(frame.AsSpan(132, 4));
        var latRaw = BinaryPrimitives.ReadInt32LittleEndian(frame.AsSpan(136, 4));
        var lonRaw = BinaryPrimitives.ReadInt32LittleEndian(frame.AsSpan(140, 4));
        var lastModified = BinaryPrimitives.ReadUInt32LittleEndian(frame.AsSpan(144, 4));

        if (string.IsNullOrWhiteSpace(name))
            name = Convert.ToHexString(publicKey.AsSpan(0, 6)).ToLowerInvariant();

        return new MeshContact(
            publicKey,
            name,
            advType,
            flags,
            outPathLength,
            lastAdvert,
            latRaw == 0 ? null : latRaw / 1_000_000.0,
            lonRaw == 0 ? null : lonRaw / 1_000_000.0,
            lastModified);
    }

    public static SentResponse DecodeSentResponse(byte[] frame)
    {
        if (frame.Length < 10 || frame[0] != RespSent)
            throw new InvalidDataException("RESP_CODE_SENT non valida.");

        return new SentResponse(
            frame[1],
            frame.AsSpan(2, 4).ToArray(),
            BinaryPrimitives.ReadUInt32LittleEndian(frame.AsSpan(6, 4)));
    }

    public static TelemetryResponse DecodeTelemetryResponse(byte[] frame)
    {
        if (frame.Length < 8 || frame[0] != PushTelemetryResponse)
            throw new InvalidDataException("PUSH_CODE_TELEMETRY_RESPONSE non valida.");

        var prefix = frame.AsSpan(2, 6).ToArray();
        var lpp = frame.AsSpan(8).ToArray();
        return new TelemetryResponse(prefix, lpp, CayenneLppDecoder.Decode(lpp));
    }

    private static string DecodeCString(ReadOnlySpan<byte> bytes)
    {
        var zero = bytes.IndexOf((byte)0);
        if (zero >= 0)
            bytes = bytes[..zero];
        return Encoding.UTF8.GetString(bytes).Trim();
    }
}

public sealed record SentResponse(byte SendType, byte[] ExpectedAckOrTag, uint SuggestedTimeoutMs);
public sealed record TelemetryResponse(byte[] PublicKeyPrefix, byte[] LppPayload, TelemetryData Decoded);
