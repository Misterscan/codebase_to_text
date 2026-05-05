import io
import os
import logging
from typing import Tuple, Optional

logger = logging.getLogger("codebase_convert")

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.webp', '.icns', '.svg'}

def is_image_file(file_path: str) -> bool:
    """Check if the file is an image based on extension"""
    return os.path.splitext(file_path)[1].lower() in IMAGE_EXTENSIONS

def compress_image(file_path: str, max_size: Tuple[int, int] = (1024, 1024), quality: int = 70, verbose: bool = False) -> Tuple[Optional[bytes], Optional[str]]:
    """Resize and compress image for smaller blob size"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            # Convert to RGB if necessary for JPEG compatibility
            if img.mode in ("RGBA", "P"):
                # Create a white background for transparent images
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if larger than max_size while maintaining aspect ratio
            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            # Save as JPEG with specified quality
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue(), "image/jpeg"
    except Exception as e:
        if verbose:
            logger.warning(f"Compression failed for {file_path}: {e}")
        return None, None
