import io
import base64
import fitz  # pymupdf
import numpy as np
from PIL import Image, ImageDraw
from typing import List, Tuple
from features.extract.models import Point, ConvertResponse, CropRequest, DesignAsset

# ── HELPERS ──

def image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def base64_to_image(b64: str) -> Image.Image:
    img_bytes = base64.b64decode(b64)
    return Image.open(io.BytesIO(img_bytes))

def polygon_to_tuples(polygon: List[Point]) -> List[Tuple[float, float]]:
    return [(p.x, p.y) for p in polygon]

# ── CONVERT PDF/IMAGE TO HIGH-RES PNG ──

def convert_file_to_image(file_bytes: bytes, filename: str) -> ConvertResponse:
    """
    Convert uploaded file (PDF or image) to a high resolution PNG.
    Returns base64 encoded image for display in frontend.
    """
    filename_lower = filename.lower()

    # Handle image files directly
    if any(filename_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]):
        try:
            img = Image.open(io.BytesIO(file_bytes))

            # Convert to RGB if needed
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # Scale up if too small for good selection
            min_dimension = 1200
            if img.width < min_dimension or img.height < min_dimension:
                scale = min_dimension / min(img.width, img.height)
                new_w = int(img.width * scale)
                new_h = int(img.height * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)

            return ConvertResponse(
                success=True,
                image_base64=image_to_base64(img),
                width=img.width,
                height=img.height,
                pages=1,
                notes="Image loaded successfully."
            )
        except Exception as e:
            return ConvertResponse(
                success=False,
                notes=f"Could not load image: {str(e)}"
            )

    # Handle PDF files
    if filename_lower.endswith(".pdf"):
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages = len(doc)

            # Use first page
            page = doc[0]

            # Render at high DPI for clear selection
            # 3x zoom ≈ 216 DPI — good balance of quality and performance
            mat = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            return ConvertResponse(
                success=True,
                image_base64=image_to_base64(img),
                width=img.width,
                height=img.height,
                pages=pages,
                notes=f"PDF rendered successfully. {pages} page(s) found. Showing page 1."
            )
        except Exception as e:
            return ConvertResponse(
                success=False,
                notes=f"Could not render PDF: {str(e)}"
            )

    return ConvertResponse(
        success=False,
        notes="Unsupported file type. Please upload a PDF, PNG, JPG, or TIFF file."
    )

# ── CROP POLYGON FROM IMAGE ──

def crop_polygon_design(req: CropRequest) -> DesignAsset:
    """
    Crop a polygon region from the full page image.

    Steps:
    1. Load the full image from base64
    2. Calculate bounding box of polygon
    3. Create a polygon mask
    4. Apply mask to image — areas outside polygon become transparent
    5. Crop to bounding box
    6. Return cropped image + mask

    The mask is saved separately for future nesting calculations —
    it represents the exact profile of the carton shape.
    """
    if len(req.polygon) < 3:
        return DesignAsset(
            success=False,
            notes="Polygon must have at least 3 points."
        )

    try:
        # Load full image
        full_img = base64_to_image(req.image_base64).convert("RGBA")
        width, height = full_img.size

        # Clamp polygon points to image bounds
        polygon_tuples = [
            (max(0, min(p.x, width - 1)),
             max(0, min(p.y, height - 1)))
            for p in req.polygon
        ]

        # Calculate bounding box
        xs = [p[0] for p in polygon_tuples]
        ys = [p[1] for p in polygon_tuples]
        bbox_x = int(min(xs))
        bbox_y = int(min(ys))
        bbox_w = int(max(xs) - min(xs))
        bbox_h = int(max(ys) - min(ys))

        # Add small padding
        padding = 10
        crop_x = max(0, bbox_x - padding)
        crop_y = max(0, bbox_y - padding)
        crop_w = min(width - crop_x, bbox_w + padding * 2)
        crop_h = min(height - crop_y, bbox_h + padding * 2)

        # Create polygon mask — white inside, black outside
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(polygon_tuples, fill=255)

        # Apply mask to image — transparent outside polygon
        masked_img = full_img.copy()
        masked_img.putalpha(mask)

        # Crop to bounding box
        cropped = masked_img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))

        # Create white background version for display
        display_img = Image.new("RGB", cropped.size, (255, 255, 255))
        display_img.paste(cropped, mask=cropped.split()[3])

        # Create mask image for nesting (just the shape)
        mask_crop = mask.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
        mask_img = Image.new("RGB", mask_crop.size, (0, 0, 0))
        mask_img.paste((255, 255, 255), mask=mask_crop)

        # Adjust polygon points relative to crop
        relative_polygon = [
            Point(x=p[0] - crop_x, y=p[1] - crop_y)
            for p in polygon_tuples
        ]

        return DesignAsset(
            success=True,
            job_id=req.job_id or "",
            cropped_image_base64=image_to_base64(display_img),
            mask_image_base64=image_to_base64(mask_img),
            polygon=relative_polygon,
            bounding_box={
                "x": crop_x, "y": crop_y,
                "w": crop_w, "h": crop_h
            },
            width=crop_w,
            height=crop_h,
            notes="Design extracted successfully. Polygon mask saved for nesting calculations."
        )

    except Exception as e:
        return DesignAsset(
            success=False,
            notes=f"Crop failed: {str(e)}"
        )
