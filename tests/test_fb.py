from PIL import Image

from mouse_jiggler.platform import fb


def test_pack_rgb565_red():
    image = Image.new("RGB", (2, 1))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (0, 0, 0))
    assert fb._pack(image, 16) == bytes([0x00, 0xF8, 0x00, 0x00])


def test_pack_bgrx_red():
    image = Image.new("RGB", (1, 1), (255, 0, 0))
    assert fb._pack(image, 32) == bytes([0x00, 0x00, 0xFF, 0x00])


def test_env_override(monkeypatch):
    monkeypatch.setenv("APPLAUNCH_LINUX_FBDEV_DEVICE", "/dev/fb7")
    assert fb.find_device() == "/dev/fb7"


def _var_buffer(xres, yres, bpp):
    import struct

    buf = bytearray(160)
    struct.pack_into("<2I", buf, 0, xres, yres)
    struct.pack_into("<4I", buf, 8, xres, yres, 0, 0)   # virtual res + offsets
    struct.pack_into("<I", buf, 24, bpp)
    return bytes(buf)


def test_parse_var_screeninfo_reads_bpp_at_offset_24():
    # Regression: the CardputerZero panel reports 320x170, 16 bpp.
    assert fb.parse_var_screeninfo(_var_buffer(320, 170, 16)) == (320, 170, 16)


def test_parse_fix_screeninfo_reads_lengths():
    import struct

    buf = bytearray(160)
    struct.pack_into("<I", buf, 24, 110592)
    struct.pack_into("<I", buf, 48, 640)
    assert fb.parse_fix_screeninfo(bytes(buf)) == (110592, 640)
