import re
import io
import pdfplumber
from pydantic import BaseModel
from features.cartons.service import BOX_STYLES

class ExtractedDimensions(BaseModel):
    success: bool
    raw_text: str = ""
    product_name: str = ""
    box_style: str = ""
    length: float = 0
    width: float = 0
    height: float = 0
    unit: str = "mm"
    confidence: str = ""
    notes: str = ""

def detect_box_style(text: str) -> str:
    text_lower = text.lower()
    if "bottom side lock" in text_lower:
        return "bottom_side_lock"
    elif "lock bottom" in text_lower or "auto bottom" in text_lower:
        return "lock_bottom"
    elif "reverse tuck" in text_lower:
        return "reverse_tuck_end"
    elif "straight tuck" in text_lower or "tuck end" in text_lower:
        return "straight_tuck_end"
    return "bottom_side_lock"

def extract_product_name(text: str) -> str:
    patterns = [
        r"Product Name\s+([A-Za-z0-9\s\(\)]+?)(?:\n|Pack|Item)",
        r"Product\s*:\s*([A-Za-z0-9\s\(\)]+?)(?:\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""

def extract_dimensions_from_text(text: str) -> dict:
    pattern1 = re.search(
        r"L[\s\-]*(\d+\.?\d*)\s*[xX×]\s*W[\s\-]*(\d+\.?\d*)\s*[xX×]\s*H[\s\-]*(\d+\.?\d*)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )
    pattern2 = re.search(
        r"L[\s\-]+(\d+\.?\d*)\s*[xX×]\s*W[\s\-]+(\d+\.?\d*)\s*[xX×]\s*H[\s\-]+(\d+\.?\d*)",
        text, re.IGNORECASE
    )
    pattern3 = re.search(
        r"(?:Dimension|Size|Foil Width)[^\n]*?L[\s\-]*(\d+\.?\d*)\s*[xX×]\s*W[\s\-]*(\d+\.?\d*)\s*[xX×]\s*H[\s\-]*(\d+\.?\d*)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )
    pattern4 = re.search(
        r"(\d+\.?\d*)\s*\(L\)\s*[xX×]\s*(\d+\.?\d*)\s*\(W\)\s*[xX×]\s*(\d+\.?\d*)\s*\(H\)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )
    pattern5 = re.search(
        r"(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*mm",
        text, re.IGNORECASE
    )

    for pattern, confidence in [
        (pattern3, "High — found in Dimension field"),
        (pattern1, "High — L x W x H format"),
        (pattern2, "High — L- W- H- format"),
        (pattern4, "High — (L) x (W) x (H) format"),
        (pattern5, "Medium — plain numbers x x mm"),
    ]:
        if pattern:
            groups = pattern.groups()
            L = float(groups[0])
            W = float(groups[1])
            H = float(groups[2])
            unit = groups[3] if len(groups) > 3 and groups[3] else "mm"
            if 10 <= L <= 500 and 10 <= W <= 500 and 10 <= H <= 500:
                return {
                    "length": L, "width": W, "height": H,
                    "unit": unit.lower() if unit else "mm",
                    "confidence": confidence
                }
    return {}

def extract_from_pdf(file_bytes: bytes) -> ExtractedDimensions:
    full_text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception as e:
        return ExtractedDimensions(
            success=False,
            notes=f"Could not read PDF: {str(e)}"
        )

    if not full_text.strip():
        return ExtractedDimensions(
            success=False,
            notes="No text found in PDF. File may be image-only."
        )

    dims = extract_dimensions_from_text(full_text)
    if not dims:
        return ExtractedDimensions(
            success=False,
            raw_text=full_text[:500],
            notes="Could not find dimension pattern. Please enter dimensions manually."
        )

    product_name = extract_product_name(full_text)
    box_style = detect_box_style(full_text)

    return ExtractedDimensions(
        success=True,
        raw_text=full_text[:500],
        product_name=product_name,
        box_style=box_style,
        length=dims["length"],
        width=dims["width"],
        height=dims["height"],
        unit=dims["unit"],
        confidence=dims["confidence"],
        notes=f"Extracted from PDF. Box style detected as: {BOX_STYLES.get(box_style, {}).get('name', box_style)}"
    )