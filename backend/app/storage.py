"""
Image storage. Uploads are decoded and re-encoded with Pillow, which validates
that the file is really an image, strips EXIF (GPS location, camera serials) and
normalises to WebP. Files go to local disk in development or to S3/MinIO.
"""
import io
import os
import secrets

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ApiError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard


def _render(img, max_side):
    copy = img.copy()
    copy.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    copy.save(buf, "WEBP", quality=82, method=4)  # saving without exif= drops all metadata
    return buf.getvalue()


def process_image(file_storage):
    raw = file_storage.read()
    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ApiError(422, "bad_image", "That file isn't a valid image.")
    if fmt not in ALLOWED_FORMATS:
        raise ApiError(422, "bad_image", "Upload JPEG, PNG or WebP images.")
    if min(img.size) < 400:
        raise ApiError(422, "bad_image", "Images must be at least 400 px on the short side.")
    return _render(img, 1600), _render(img, 480)


def save(listing_public_id, full, thumb):
    name = secrets.token_hex(12)
    keys = (f"listings/{listing_public_id}/{name}.webp", f"listings/{listing_public_id}/{name}_t.webp")
    cfg = current_app.config
    if cfg.get("S3_BUCKET"):
        import boto3
        s3 = boto3.client("s3", endpoint_url=cfg.get("S3_ENDPOINT_URL"))
        for key, data in zip(keys, (full, thumb)):
            s3.put_object(Bucket=cfg["S3_BUCKET"], Key=key, Body=data, ContentType="image/webp",
                          CacheControl="public, max-age=31536000, immutable")
        base = cfg.get("S3_PUBLIC_URL") or f"https://{cfg['S3_BUCKET']}.s3.amazonaws.com"
        return [f"{base}/{k}" for k in keys]
    for key, data in zip(keys, (full, thumb)):
        path = os.path.join(cfg["UPLOAD_DIR"], key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return [f"{cfg['MEDIA_URL']}/{k}" for k in keys]
