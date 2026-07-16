"""
Screen capture for RMM agent.
Captures primary display as JPEG bytes.

Platform support:
  Windows: PIL.ImageGrab (built-in with Pillow)
  macOS:   PIL.ImageGrab (Pillow >= 9.x, requires Screen Recording permission)
  Linux:   PIL.ImageGrab with display env, or scrot subprocess fallback
"""
import io
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_MAX_WIDTH = 1920
_JPEG_QUALITY = 72


def capture(max_width: int = _MAX_WIDTH, quality: int = _JPEG_QUALITY) -> bytes | None:
    """Return JPEG bytes of the primary screen, or None on failure."""
    if sys.platform == "win32" or sys.platform == "darwin":
        return _capture_pillow(max_width, quality)
    return _capture_linux(max_width, quality)


def _capture_pillow(max_width: int, quality: int) -> bytes | None:
    try:
        from PIL import ImageGrab, Image
        img = ImageGrab.grab()
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception as exc:
        logger.debug("Pillow screenshot failed: %s", exc)
        return None


def _capture_linux(max_width: int, quality: int) -> bytes | None:
    # Try scrot (most common on X11 desktops)
    jpeg = _capture_scrot()
    if jpeg:
        return _resize_jpeg(jpeg, max_width, quality)

    # Try gnome-screenshot
    jpeg = _capture_gnome()
    if jpeg:
        return _resize_jpeg(jpeg, max_width, quality)

    # Try Pillow as last resort (needs DISPLAY set)
    return _capture_pillow(max_width, quality)


def _capture_scrot() -> bytes | None:
    try:
        result = subprocess.run(
            ["scrot", "-"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return None


def _capture_gnome() -> bytes | None:
    import tempfile
    import os
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        result = subprocess.run(
            ["gnome-screenshot", "-f", tmp],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and os.path.exists(tmp):
            with open(tmp, "rb") as f:
                data = f.read()
            os.unlink(tmp)
            return data
    except Exception:
        pass
    return None


def _resize_jpeg(png_or_jpeg: bytes, max_width: int, quality: int) -> bytes | None:
    try:
        from PIL import Image
        buf_in = io.BytesIO(png_or_jpeg)
        img = Image.open(buf_in)
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf_out = io.BytesIO()
        img.save(buf_out, format="JPEG", quality=quality, optimize=True)
        return buf_out.getvalue()
    except Exception as exc:
        logger.debug("Image resize failed: %s", exc)
        return png_or_jpeg  # return as-is rather than drop
