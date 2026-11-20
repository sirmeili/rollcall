"""Re-encoding a photo: the email copy is a JPEG at most 1024 px on its long side, whatever
the full photo's format. The API never serves it; the status emails attach it (#157)."""

import io

from PIL import Image

from filament_tracker.print_requests.photos import reencode


def _encoded(image: Image.Image, image_format: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, image_format)
    return buffer.getvalue()


def _opened(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def test_a_large_photo_gets_an_email_copy_1024_px_on_its_long_side() -> None:
    photo = reencode(_encoded(Image.new("RGB", (3000, 1500), (10, 120, 200)), "JPEG"))

    full, email = _opened(photo.full), _opened(photo.email)
    assert (full.format, full.size) == ("JPEG", (3000, 1500))
    assert (email.format, email.size) == ("JPEG", (1024, 512))


def test_a_small_photo_keeps_its_size_in_the_email_copy() -> None:
    photo = reencode(_encoded(Image.new("RGB", (600, 800)), "PNG"))

    assert _opened(photo.email).size == (600, 800)


def test_a_transparent_png_is_laid_over_white_in_the_email_copy() -> None:
    clear = Image.new("RGBA", (20, 20), (0, 0, 0, 0))

    photo = reencode(_encoded(clear, "PNG"))

    assert (photo.suffix, _opened(photo.full).mode) == (".png", "RGBA")
    email = _opened(photo.email)
    assert email.format == "JPEG"
    assert email.getpixel((10, 10)) == (255, 255, 255)


def test_a_palette_png_gets_an_email_copy_too() -> None:
    photo = reencode(_encoded(Image.new("P", (16, 16)), "PNG"))

    assert _opened(photo.email).mode == "RGB"


def test_a_grayscale_jpeg_stays_a_jpeg() -> None:
    photo = reencode(_encoded(Image.new("L", (16, 16), 128), "JPEG"))

    assert (photo.suffix, _opened(photo.full).mode, _opened(photo.email).mode) == (
        ".jpg",
        "L",
        "RGB",
    )
