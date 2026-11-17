"""Linux framebuffer access for the 320x170 ST7789V panel.

The CardputerZero exposes the LCD as ``/dev/fb1`` on most images (``fb0`` may be
HDMI), so the device is discovered through sysfs rather than hard-coded.
"""

from __future__ import annotations

import fcntl
import glob
import logging
import mmap
import os
import struct

from PIL import Image

log = logging.getLogger(__name__)

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602


class FramebufferError(RuntimeError):
    pass


def parse_var_screeninfo(buf: bytes) -> tuple[int, int, int]:
    """Return (xres, yres, bits_per_pixel) from struct fb_var_screeninfo."""
    xres, yres = struct.unpack_from("<2I", buf, 0)
    bpp = struct.unpack_from("<I", buf, 24)[0]
    return xres, yres, bpp


def parse_fix_screeninfo(buf: bytes) -> tuple[int, int]:
    """Return (smem_len, line_length) from struct fb_fix_screeninfo."""
    smem_len = struct.unpack_from("<I", buf, 24)[0]
    line_length = struct.unpack_from("<I", buf, 48)[0]
    return smem_len, line_length


def find_device() -> str:
    for var in ("APPLAUNCH_LINUX_FBDEV_DEVICE", "LV_LINUX_FBDEV_DEVICE"):
        value = os.environ.get(var)
        if value:
            return value
    for sysfs in sorted(glob.glob("/sys/class/graphics/fb*")):
        try:
            with open(os.path.join(sysfs, "name"), encoding="utf-8") as fh:
                name = fh.read().strip().lower()
        except OSError:
            continue
        if "st7789" in name:
            return "/dev/" + os.path.basename(sysfs)
    return "/dev/fb0"


class Framebuffer:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or find_device()
        self.fd = -1
        self.width = 0
        self.height = 0
        self.bpp = 0
        self.line_length = 0
        self._map: mmap.mmap | None = None

    def open(self) -> Framebuffer:
        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except OSError as exc:
            raise FramebufferError(f"cannot open {self.path}: {exc}") from exc
        try:
            var = bytearray(160)
            fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, var)
            self.width, self.height, self.bpp = parse_var_screeninfo(var)

            fix = bytearray(160)
            fcntl.ioctl(self.fd, FBIOGET_FSCREENINFO, fix)
            smem_len, line_length = parse_fix_screeninfo(fix)
            self.line_length = line_length or self.width * (self.bpp // 8)

            if self.bpp not in (16, 32):
                raise FramebufferError(f"unsupported framebuffer depth: {self.bpp} bpp")
            size = max(smem_len, self.line_length * self.height)
            self._map = mmap.mmap(self.fd, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        except (OSError, ValueError) as exc:
            self.close()
            raise FramebufferError(f"cannot map {self.path}: {exc}") from exc

        log.info("framebuffer %s: %dx%d %dbpp line_length=%d",
                 self.path, self.width, self.height, self.bpp, self.line_length)
        return self

    def show(self, image: Image.Image) -> None:
        if self._map is None:
            raise FramebufferError("framebuffer is not open")
        if image.size != (self.width, self.height):
            raise FramebufferError(
                f"image is {image.size[0]}x{image.size[1]}, panel is {self.width}x{self.height}"
            )
        frame = _pack(image, self.bpp)
        row = self.width * (self.bpp // 8)
        if self.line_length == row:
            self._map.seek(0)
            self._map.write(frame)
            return
        for y in range(self.height):
            self._map.seek(y * self.line_length)
            self._map.write(frame[y * row:(y + 1) * row])

    def close(self) -> None:
        if self._map is not None:
            try:
                self._map.close()
            except (BufferError, ValueError):
                pass
            self._map = None
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1


def _pack(image: Image.Image, bpp: int) -> bytes:
    if bpp == 32:
        return image.tobytes("raw", "BGRX")
    return _rgb565(image)


def _rgb565(image: Image.Image) -> bytes:
    try:
        import numpy as np
    except ImportError:
        out = bytearray(image.width * image.height * 2)
        pixels = image.load()
        index = 0
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = pixels[x, y]
                value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                out[index] = value & 0xFF
                out[index + 1] = value >> 8
                index += 2
        return bytes(out)

    array = np.asarray(image, dtype=np.uint16)
    value = ((array[..., 0] >> 3) << 11) | ((array[..., 1] >> 2) << 5) | (array[..., 2] >> 3)
    return value.astype("<u2").tobytes()
