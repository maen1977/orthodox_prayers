from pathlib import Path
import struct
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _read_rgba_png(path: Path) -> tuple[int, int, bytes]:
    """Decode the exact PNG profile used by the adaptive foreground.

    This deliberately uses only the Python standard library so the release
    quality gate does not depend on Pillow merely to inspect one RGBA asset.
    """

    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise AssertionError(f"not a PNG file: {path}")

    offset = len(PNG_SIGNATURE)
    width = height = None
    compressed_parts: list[bytes] = []
    while offset < len(data):
        if offset + 12 > len(data):
            raise AssertionError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + length
        if chunk_end + 4 > len(data):
            raise AssertionError("truncated PNG chunk payload")
        payload = data[chunk_start:chunk_end]
        offset = chunk_end + 4  # Skip CRC after payload.

        if chunk_type == b"IHDR":
            if len(payload) != 13:
                raise AssertionError("invalid IHDR length")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (bit_depth, color_type, compression, filtering, interlace) != (8, 6, 0, 0, 0):
                raise AssertionError(
                    "foreground PNG must be non-interlaced 8-bit RGBA"
                )
        elif chunk_type == b"IDAT":
            compressed_parts.append(payload)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or not compressed_parts:
        raise AssertionError("PNG is missing IHDR or IDAT")

    bytes_per_pixel = 4
    stride = width * bytes_per_pixel
    raw = zlib.decompress(b"".join(compressed_parts))
    expected_length = height * (stride + 1)
    if len(raw) != expected_length:
        raise AssertionError(
            f"unexpected decoded PNG length: {len(raw)} != {expected_length}"
        )

    pixels = bytearray(height * stride)
    previous = bytearray(stride)
    source_offset = 0
    for row_index in range(height):
        filter_type = raw[source_offset]
        source_offset += 1
        filtered = raw[source_offset : source_offset + stride]
        source_offset += stride
        current = bytearray(stride)

        for index, value in enumerate(filtered):
            left = current[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            above = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 0:
                reconstructed = value
            elif filter_type == 1:
                reconstructed = value + left
            elif filter_type == 2:
                reconstructed = value + above
            elif filter_type == 3:
                reconstructed = value + ((left + above) // 2)
            elif filter_type == 4:
                reconstructed = value + _paeth_predictor(left, above, upper_left)
            else:
                raise AssertionError(f"unsupported PNG filter: {filter_type}")
            current[index] = reconstructed & 0xFF

        destination = row_index * stride
        pixels[destination : destination + stride] = current
        previous = current

    return width, height, bytes(pixels)


def _alpha_bbox(width: int, height: int, rgba: bytes) -> tuple[int, int, int, int] | None:
    xs: list[int] = []
    ys: list[int] = []
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            if rgba[row + x * 4 + 3] != 0:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


class IconSafeZoneTests(unittest.TestCase):
    def test_foreground_is_108_canvas_and_art_fits_compact_safe_zone(self) -> None:
        path = ROOT / "app/src/main/res/drawable-nodpi/church_prayers_cross_foreground.png"
        width, height, rgba = _read_rgba_png(path)
        self.assertEqual((108, 108), (width, height))
        box = _alpha_bbox(width, height, rgba)
        self.assertIsNotNone(box)
        assert box is not None
        self.assertLessEqual(box[2] - box[0], 50)
        self.assertLessEqual(box[3] - box[1], 56)

    def test_adaptive_layer_uses_safe_foreground(self) -> None:
        text = (
            ROOT / "app/src/main/res/drawable/ic_launcher_foreground.xml"
        ).read_text(encoding="utf-8")
        self.assertIn("@drawable/church_prayers_cross_foreground", text)
        self.assertNotIn("20dp", text)
        monochrome = (ROOT / "app/src/main/res/drawable/ic_launcher_monochrome.xml").read_text(encoding="utf-8")
        self.assertIn('android:scaleX="0.82"', monochrome)
        self.assertIn('android:scaleY="0.82"', monochrome)




if __name__ == "__main__":
    unittest.main()
