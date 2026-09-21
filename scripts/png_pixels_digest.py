#!/usr/bin/env python3
"""Hash decoded image pixels while ignoring PNG metadata."""
import hashlib
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def digest(path):
    data = decode_bmp(path)
    return hashlib.md5(data["shape"] + data["pixels"]).hexdigest()


def decode_bmp(path):
    with tempfile.TemporaryDirectory(prefix="ipb-pixels-") as directory:
        bmp = Path(directory) / "decoded.bmp"
        subprocess.run(["sips", "-s", "format", "bmp", str(path), "--out", str(bmp)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        data = bmp.read_bytes()
    if data[:2] != b"BM" or len(data) < 14:
        raise ValueError("sips did not produce a BMP")
    offset = struct.unpack_from("<I", data, 10)[0]
    if offset >= len(data) or len(data) < 54:
        raise ValueError("BMP pixel offset is outside the file")
    width, raw_height, planes, bits, compression = struct.unpack_from("<iiHHI", data, 18)
    if width <= 0 or raw_height == 0 or planes != 1 or compression not in (0, 3) or bits not in (24, 32):
        raise ValueError("unsupported BMP dimensions or pixel format")
    if compression == 3 and data[54:66] != bytes.fromhex("0000ff0000ff0000ff000000"):
        raise ValueError("unsupported BMP bitfield masks")
    height = abs(raw_height)
    row_bytes = ((width * bits + 31) // 32) * 4
    if offset + row_bytes * height > len(data):
        raise ValueError("BMP pixel payload is truncated")
    rows = []
    for y in range(height):
        source_y = y if raw_height < 0 else height - 1 - y
        row = data[offset + source_y * row_bytes:offset + (source_y + 1) * row_bytes]
        pixels = bytearray()
        for x in range(width):
            base = x * (bits // 8)
            pixels.extend((row[base + 2], row[base + 1], row[base]))
        rows.append(bytes(pixels))
    return {"width": width, "height": height, "shape": struct.pack(">IIH", width, height, bits), "pixels": b"".join(rows)}


def difference_ratio(path_a, path_b):
    first, second = decode_bmp(path_a), decode_bmp(path_b)
    if (first["width"], first["height"]) != (second["width"], second["height"]):
        raise ValueError("image dimensions differ")
    # Three channel bytes per pixel; count a pixel once if any channel moves.
    pixels = first["width"] * first["height"]
    changed_pixels = sum(
        1 for index in range(0, len(first["pixels"]), 3)
        if max(abs(first["pixels"][index + channel] - second["pixels"][index + channel]) for channel in range(3)) >= 16
    )
    return changed_pixels / pixels if pixels else 0.0


if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--difference":
            print("%.6f" % difference_ratio(sys.argv[2], sys.argv[3]))
        else:
            print(digest(sys.argv[1]))
    except (IndexError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print("png_pixels_digest: %s" % error, file=sys.stderr)
        raise SystemExit(2)
