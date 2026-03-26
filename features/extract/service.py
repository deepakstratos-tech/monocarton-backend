import re
import io
import pdfplumber
import fitz  # pymupdf
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
    extraction_method: str = ""

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
        r"Product Name\s+([A-Za-z0-9\s\(\)\-]+?)(?:\n|Pack|Item|Customer)",
        r"Product\s*:\s*([A-Za-z0-9\s\(\)\-]+?)(?:\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) > 2:
                return name
    return ""

def extract_dimensions_from_text(text: str) -> dict:
    """Try multiple dimension patterns."""

    # Pattern 1: "L 57 x W 57 x H 157 mm"
    pattern1 = re.search(
        r"L[\s\-]*(\d+\.?\d*)\s*[xX×]\s*W[\s\-]*(\d+\.?\d*)\s*[xX×]\s*H[\s\-]*(\d+\.?\d*)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )

    # Pattern 2: "L- 57 x W- 57 x H- 157"
    pattern2 = re.search(
        r"L[\s\-]+(\d+\.?\d*)\s*[xX×]\s*W[\s\-]+(\d+\.?\d*)\s*[xX×]\s*H[\s\-]+(\d+\.?\d*)",
        text, re.IGNORECASE
    )

    # Pattern 3: "Dimension/Foil Width L 57 x W 57 x H 157 mm"
    pattern3 = re.search(
        r"(?:Dimension|Size|Foil Width)[^\n]*?L[\s\-]*(\d+\.?\d*)\s*[xX×]\s*W[\s\-]*(\d+\.?\d*)\s*[xX×]\s*H[\s\-]*(\d+\.?\d*)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )

    # Pattern 4: "110 (L) x 88 (W) x 140 (H)"
    pattern4 = re.search(
        r"(\d+\.?\d*)\s*\(L\)\s*[xX×]\s*(\d+\.?\d*)\s*\(W\)\s*[xX×]\s*(\d+\.?\d*)\s*\(H\)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )

    # Pattern 5: "45 x 45 x 83 mm"
    pattern5 = re.search(
        r"(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*mm",
        text, re.IGNORECASE
    )

    # Pattern 6: "Outer Size : 45 (L) x 45 (W) x 83 (H) mm"
    pattern6 = re.search(
        r"(?:Outer|Overall|Box|Carton)\s+Size\s*[:\-]?\s*(\d+\.?\d*)\s*[xX×\(L\)]*\s*(\d+\.?\d*)\s*[xX×\(W\)]*\s*(\d+\.?\d*)\s*(mm|cm|in)?",
        text, re.IGNORECASE
    )

    # Pattern 7: Specifically for "45 (L) x 45 (W) x 83 (H) mm" format
    pattern7 = re.search(
        r"(\d+)\s*\(L\)\s*[xX×]\s*(\d+)\s*\(W\)\s*[xX×]\s*(\d+)\s*\(H\)\s*mm",
        text, re.IGNORECASE
    )

    # Pattern 8: L=45 W=45 H=83
    pattern8 = re.search(
        r"L\s*[:=]\s*(\d+\.?\d*).*?W\s*[:=]\s*(\d+\.?\d*).*?H\s*[:=]\s*(\d+\.?\d*)",
        text, re.IGNORECASE
    )

    for pattern, confidence in [
        (pattern7, "High — (L) x (W) x (H) mm format"),
        (pattern3, "High — found in Dimension field"),
        (pattern4, "High — (L) x (W) x (H) format"),
        (pattern1, "High — L x W x H format"),
        (pattern2, "High — L- W- H- format"),
        (pattern6, "High — Outer Size format"),
        (pattern8, "Medium — L: W: H: format"),
        (pattern5, "Medium — plain numbers x x mm"),
    ]:
        if pattern:
            groups = pattern.groups()
            try:
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
            except (ValueError, IndexError):
                continue
    return {}

# ── METHOD 1: pdfplumber ──

def extract_text_pdfplumber(file_bytes: bytes) -> str:
    """Standard text extraction with pdfplumber."""
    full_text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                # Try standard text extraction
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

                # Try word extraction as fallback
                if not text:
                    words = page.extract_words()
                    if words:
                        full_text += " ".join([w["text"] for w in words]) + "\n"

                # Try table extraction for structured data
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            row_text = " ".join([str(cell) for cell in row if cell])
                            full_text += row_text + "\n"
    except Exception:
        pass
    return full_text.strip()

# ── METHOD 2: pymupdf ──

def extract_text_pymupdf(file_bytes: bytes) -> str:
    """
    Extract text using pymupdf (fitz).
    Much better at handling complex PDF layouts,
    embedded fonts, and non-standard text encoding.
    """
    full_text = ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # Method A: standard text extraction
            text = page.get_text("text")
            if text.strip():
                full_text += text + "\n"

            # Method B: extract as blocks — better for tables
            if not text.strip():
                blocks = page.get_text("blocks")
                for block in blocks:
                    if block[6] == 0:  # text block
                        full_text += block[4] + "\n"

            # Method C: extract as dict — gets all text including
            # text in different positions and orientations
            if not full_text.strip():
                text_dict = page.get_text("dict")
                for block in text_dict.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            full_text += span.get("text", "") + " "
                        full_text += "\n"

        doc.close()
    except Exception:
        pass
    return full_text.strip()

# ── METHOD 3: pymupdf rawdict — deepest extraction ──

def extract_text_pymupdf_raw(file_bytes: bytes) -> str:
    """
    Deep extraction using pymupdf rawdict.
    Catches text that other methods miss — especially
    text rendered as paths or with unusual encodings.
    """
    full_text = ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # rawdict extracts every character individually
            raw = page.get_text("rawdict")
            for block in raw.get("blocks", []):
                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        for char in span.get("chars", []):
                            line_text += char.get("c", "")
                    if line_text.strip():
                        full_text += line_text + "\n"
        doc.close()
    except Exception:
        pass
    return full_text.strip()

# ── MAIN EXTRACTION FUNCTION ──

def extract_from_pdf(file_bytes: bytes) -> ExtractedDimensions:
    """
    Try multiple extraction methods in order:
    1. pdfplumber — standard text PDFs
    2. pymupdf text — complex layouts
    3. pymupdf blocks — table-heavy PDFs
    4. pymupdf rawdict — deepest extraction
    """
    methods = [
        ("pdfplumber", extract_text_pdfplumber),
        ("pymupdf", extract_text_pymupdf),
        ("pymupdf_raw", extract_text_pymupdf_raw),
    ]

    best_text = ""
    best_method = "none"

    # Try each method — use the one that gives the most text
    for method_name, method_fn in methods:
        text = method_fn(file_bytes)
        if len(text) > len(best_text):
            best_text = text
            best_method = method_name

        # If we already found dimensions, stop early
        if text and extract_dimensions_from_text(text):
            best_text = text
            best_method = method_name
            break

    if not best_text:
        return ExtractedDimensions(
            success=False,
            notes=(
                "No text could be extracted from this PDF. "
                "This may be a fully image-based PDF. "
                "Please enter dimensions manually."
            ),
            extraction_method="none"
        )

    # Try to extract dimensions
    dims = extract_dimensions_from_text(best_text)

    if not dims:
        return ExtractedDimensions(
            success=False,
            raw_text=best_text[:800],
            extraction_method=best_method,
            notes=(
                "Text was extracted but no dimension pattern was found. "
                "Review the extracted text below and enter dimensions manually."
            )
        )

    product_name = extract_product_name(best_text)
    box_style = detect_box_style(best_text)

    return ExtractedDimensions(
        success=True,
        raw_text=best_text[:800],
        product_name=product_name,
        box_style=box_style,
        length=dims["length"],
        width=dims["width"],
        height=dims["height"],
        unit=dims["unit"],
        confidence=dims["confidence"],
        extraction_method=best_method,
        notes=(
            f"Extracted using {best_method}. "
            f"Box style detected as: {BOX_STYLES.get(box_style, {}).get('name', box_style)}"
        )
    )
