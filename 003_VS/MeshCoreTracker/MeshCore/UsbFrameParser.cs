namespace MeshCoreTracker.MeshCore;

public sealed class UsbFrameParser
{
    private readonly List<byte> _buffer = [];
    private const byte FromRadio = (byte)'>';

    public IReadOnlyList<byte[]> Feed(ReadOnlySpan<byte> data)
    {
        foreach (var b in data)
            _buffer.Add(b);

        var frames = new List<byte[]>();

        while (true)
        {
            var marker = _buffer.IndexOf(FromRadio);
            if (marker < 0)
            {
                _buffer.Clear();
                break;
            }

            if (marker > 0)
                _buffer.RemoveRange(0, marker);

            if (_buffer.Count < 3)
                break;

            var length = _buffer[1] | (_buffer[2] << 8);
            var total = 3 + length;
            if (_buffer.Count < total)
                break;

            frames.Add(_buffer.GetRange(3, length).ToArray());
            _buffer.RemoveRange(0, total);
        }

        return frames;
    }
}
