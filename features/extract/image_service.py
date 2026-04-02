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

# ── BOX STYLE DETECTION FROM POLYGON ──

BOX_STYLE_NAMES = {
    "bottom_side_lock": "Bottom Side Lock",
    "straight_tuck_end": "Straight Tuck End",
    "reverse_tuck_end": "Reverse Tuck End",
    "lock_bottom": "Lock Bottom",
}

# Known signatures: (top_ratio_min, top_ratio_max, bottom_ratio_min, bottom_ratio_max)
BOX_STYLE_SIGNATURES = {
    "bottom_side_lock": {
        "top_min": 0.14, "top_max": 0.28,
        "bot_min": 0.20, "bot_max": 0.38,
        "description": "Top tuck ~20–25% of flat height, bottom lock ~25–35%"
    },
    "straight_tuck_end": {
        "top_min": 0.12, "top_max": 0.24,
        "bot_min": 0.12, "bot_max": 0.24,
        "description": "Top and bottom tucks roughly equal ~15–22% each"
    },
    "reverse_tuck_end": {
        "top_min": 0.12, "top_max": 0.24,
        "bot_min": 0.12, "bot_max": 0.24,
        "description": "Same ratios as straight tuck — style determined by artwork orientation"
    },
    "lock_bottom": {
        "top_min": 0.14, "top_max": 0.28,
        "bot_min": 0.28, "bot_max": 0.45,
        "description": "Top tuck ~20–25%, deep auto-lock bottom ~35–40%"
    },
}

def detect_box_style_from_polygon(
    polygon: List[Point],
    image_width: int,
    image_height: int,
    declared_style: str
) -> dict:
    """
    Analyse polygon shape to detect box style.

    Algorithm:
    1. Get bounding box of polygon
    2. Find the body region — widest horizontal span
    3. Measure top flap height (above body)
    4. Measure bottom flap height (below body)
    5. Calculate ratios and match against known signatures
    """
    from features.extract.models import BoxStyleDetectionResult

    if len(polygon) < 4:
        return BoxStyleDetectionResult(
            detected_style=declared_style,
            detected_style_name=BOX_STYLE_NAMES.get(declared_style, declared_style),
            declared_style=declared_style,
            declared_style_name=BOX_STYLE_NAMES.get(declared_style, declared_style),
            confidence="Low",
            match=True,
            suggestion="Not enough polygon points to analyse shape. Please draw at least 4 points.",
            top_ratio=0, bottom_ratio=0,
            analysis_notes="Insufficient polygon data."
        )

    xs = [p.x for p in polygon]
    ys = [p.y for p in polygon]

    total_h = max(ys) - min(ys)
    total_w = max(xs) - min(xs)
    y_min = min(ys)
    y_max = max(ys)

    if total_h == 0:
        return BoxStyleDetectionResult(
            detected_style=declared_style,
            detected_style_name=BOX_STYLE_NAMES.get(declared_style, declared_style),
            declared_style=declared_style,
            declared_style_name=BOX_STYLE_NAMES.get(declared_style, declared_style),
            confidence="Low",
            match=True,
            suggestion="Could not analyse polygon — zero height detected.",
            top_ratio=0, bottom_ratio=0,
            analysis_notes="Zero height polygon."
        )

    # Divide polygon into horizontal slices
    # Find width at each 5% increment of height
    num_slices = 20
    slice_widths = []

    for i in range(num_slices):
        y_level = y_min + (i / num_slices) * total_h
        # Find all polygon edges that cross this y level
        widths_at_y = []
        n = len(polygon)
        for j in range(n):
            p1 = polygon[j]
            p2 = polygon[(j + 1) % n]
            if min(p1.y, p2.y) <= y_level <= max(p1.y, p2.y):
                if p2.y != p1.y:
                    # Interpolate x at this y level
                    t = (y_level - p1.y) / (p2.y - p1.y)
                    x_intersect = p1.x + t * (p2.x - p1.x)
                    widths_at_y.append(x_intersect)

        if len(widths_at_y) >= 2:
            slice_widths.append({
                "slice": i,
                "y_pct": i / num_slices,
                "width": max(widths_at_y) - min(widths_at_y)
            })

    if not slice_widths:
        return BoxStyleDetectionResult(
            detected_style=declared_style,
            detected_style_name=BOX_STYLE_NAMES.get(declared_style, declared_style),
            declared_style=declared_style,
            declared_style_name=BOX_STYLE_NAMES.get(declared_style, declared_style),
            confidence="Low",
            match=True,
            suggestion="Could not analyse polygon cross-sections.",
            top_ratio=0, bottom_ratio=0,
            analysis_notes="No valid cross-sections found."
        )

    max_width = max(s["width"] for s in slice_widths)
    body_threshold = max_width * 0.75

    # Find top of body — first slice that reaches body width
    body_start_pct = 0
    for s in slice_widths:
        if s["width"] >= body_threshold:
            body_start_pct = s["y_pct"]
            break

    # Find bottom of body — last slice that maintains body width
    body_end_pct = 1.0
    for s in reversed(slice_widths):
        if s["width"] >= body_threshold:
            body_end_pct = s["y_pct"]
            break

    top_ratio = round(body_start_pct, 3)
    bottom_ratio = round(1.0 - body_end_pct, 3)

    # Match against known signatures
    scores = {}
    for style, sig in BOX_STYLE_SIGNATURES.items():
        top_match = sig["top_min"] <= top_ratio <= sig["top_max"]
        bot_match = sig["bot_min"] <= bottom_ratio <= sig["bot_max"]

        if top_match and bot_match:
            scores[style] = 2
        elif top_match or bot_match:
            scores[style] = 1
        else:
            # Partial score based on distance from range
            top_dist = max(0, sig["top_min"] - top_ratio,
                          top_ratio - sig["top_max"])
            bot_dist = max(0, sig["bot_min"] - bottom_ratio,
                          bottom_ratio - sig["bot_max"])
            scores[style] = max(0, 1 - (top_dist + bot_dist) * 5)

    # Straight and reverse tuck have same ratios
    # Can't distinguish from shape alone
    if scores.get("straight_tuck_end", 0) > 0:
        scores["reverse_tuck_end"] = scores["straight_tuck_end"]

    detected_style = max(scores, key=scores.get)
    best_score = scores[detected_style]

    # Confidence
    if best_score == 2:
        confidence = "High"
    elif best_score >= 1:
        confidence = "Medium"
    else:
        confidence = "Low"

    match = detected_style == declared_style

    # Build suggestion message
    declared_name = BOX_STYLE_NAMES.get(declared_style, declared_style)
    detected_name = BOX_STYLE_NAMES.get(detected_style, detected_style)

    if match:
        suggestion = (
            f"✅ Box style confirmed. Polygon shape is consistent with "
            f"{declared_name} — top flap ratio {top_ratio:.1%}, "
            f"bottom flap ratio {bottom_ratio:.1%}."
        )
    elif confidence == "Low":
        suggestion = (
            f"⚠️ Low confidence analysis. You selected {declared_name}. "
            f"Polygon shape is ambiguous — top {top_ratio:.1%}, bottom {bottom_ratio:.1%}. "
            f"Verify the box style manually."
        )
    else:
        suggestion = (
            f"⚠️ Possible mismatch. You selected {declared_name} but the polygon "
            f"shape suggests {detected_name} — "
            f"top flap ratio {top_ratio:.1%} (expected "
            f"{BOX_STYLE_SIGNATURES[declared_style]['top_min']:.0%}–"
            f"{BOX_STYLE_SIGNATURES[declared_style]['top_max']:.0%}), "
            f"bottom ratio {bottom_ratio:.1%} (expected "
            f"{BOX_STYLE_SIGNATURES[declared_style]['bot_min']:.0%}–"
            f"{BOX_STYLE_SIGNATURES[declared_style]['bot_max']:.0%}). "
            f"Consider changing to {detected_name}."
        )

    analysis_notes = (
        f"Top ratio: {top_ratio:.3f} | Bottom ratio: {bottom_ratio:.3f} | "
        f"Body threshold: {body_threshold:.1f}px | "
        f"Body starts at: {body_start_pct:.1%} | Body ends at: {body_end_pct:.1%} | "
        f"Scores: {scores}"
    )

    return BoxStyleDetectionResult(
        detected_style=detected_style,
        detected_style_name=detected_name,
        declared_style=declared_style,
        declared_style_name=declared_name,
        confidence=confidence,
        match=match,
        suggestion=suggestion,
        top_ratio=top_ratio,
        bottom_ratio=bottom_ratio,
        analysis_notes=analysis_notes,
    )