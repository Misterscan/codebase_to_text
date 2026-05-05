import io
import logging
import os
from typing import Optional, Tuple

from PIL import Image, ImageFile, UnidentifiedImageError

logger = logging.getLogger("codebase_convert")

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".ico",
    ".webp",
}

MAX_IMAGE_BYTES = int(os.environ.get("CODEBASE_CONVERT_MAX_IMAGE_BYTES", "5000000"))
MAX_IMAGE_PIXELS = int(os.environ.get("CODEBASE_CONVERT_MAX_IMAGE_PIXELS", "20000000"))

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
ImageFile.LOAD_TRUNCATED_IMAGES = False


def is_image_file(file_path: str) -> bool:
    """Check if the file is a supported raster image based on extension."""
    return os.path.splitext(file_path)[1].lower() in IMAGE_EXTENSIONS


def compress_image(
    file_path: str,
    max_size: Tuple[int, int] = (1024, 1024),
    quality: int = 70,
    verbose: bool = False,
) -> Tuple[Optional[bytes], Optional[str]]:
    """Resize and compress image for smaller blob size."""
    try:
        if os.path.getsize(file_path) > MAX_IMAGE_BYTES:
            if verbose:
                logger.warning(f"Image too large to process safely: {file_path}")
            return None, None

        with Image.open(file_path) as img:
            img.verify()

        with Image.open(file_path) as img:
            img.load()

            if img.width * img.height > MAX_IMAGE_PIXELS:
                if verbose:
                    logger.warning(f"Image pixel count too large to process safely: {file_path}")
                return None, None

            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))

                if img.mode in ("RGBA", "LA"):
                    alpha = img.getchannel("A")
                    background.paste(img.convert("RGBA"), mask=alpha)
                else:
                    background.paste(img.convert("RGB"))

                img = background

            elif img.mode != "RGB":
                img = img.convert("RGB")

            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)

            return output.getvalue(), "image/jpeg"

    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as e:
        if verbose:
            logger.warning(f"Compression failed for {file_path}: {e}")
        return None, None