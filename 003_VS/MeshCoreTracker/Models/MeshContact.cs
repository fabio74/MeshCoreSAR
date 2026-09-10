namespace MeshCoreTracker.Models;

public sealed record MeshContact(
    byte[] PublicKey,
    string Name,
    byte AdvType,
    byte Flags,
    sbyte OutPathLength,
    uint LastAdvert,
    double? AdvertLatitude,
    double? AdvertLongitude,
    uint LastModified)
{
    public string KeyHex => Convert.ToHexString(PublicKey).ToLowerInvariant();
    public byte[] Prefix => PublicKey.Take(6).ToArray();
}
