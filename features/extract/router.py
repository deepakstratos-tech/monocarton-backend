from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from features.extract.service import ExtractedDimensions, extract_from_pdf
from features.extract.models import CropRequest, ConvertResponse, DesignAsset
from features.extract.image_service import convert_file_to_image, crop_polygon_design
from features.extract.models import BoxStyleDetectionRequest, BoxStyleDetectionResult
from features.extract.image_service import detect_box_style_from_polygon

router = APIRouter()

@router.post("/pdf", response_model=ExtractedDimensions)
async def extract_pdf_dimensions(file: UploadFile = File(...)):
    """Extract carton dimensions from PDF artwork file using text extraction."""
    if not file.filename.lower().endswith(".pdf"):
        return ExtractedDimensions(
            success=False,
            notes="Please upload a PDF file."
        )
    file_bytes = await file.read()
    return extract_from_pdf(file_bytes)

@router.post("/convert", response_model=ConvertResponse)
async def convert_to_image(file: UploadFile = File(...)):
    """
    Convert uploaded PDF or image file to a high resolution PNG.
    Returns base64 encoded image for display in the design selector.
    Accepts: PDF, PNG, JPG, JPEG, TIFF, BMP
    """
    file_bytes = await file.read()
    return convert_file_to_image(file_bytes, file.filename)

@router.post("/crop-design", response_model=DesignAsset)
async def crop_design(req: CropRequest):
    """
    Crop a polygon region from a full page image.
    Receives the full image as base64 and polygon coordinates.
    Returns cropped design image and polygon mask for nesting.
    """
    return crop_polygon_design(req)

@router.post("/detect-box-style", response_model=BoxStyleDetectionResult)
async def detect_box_style(req: BoxStyleDetectionRequest):
    """
    Analyse a polygon drawn around a carton dieline and detect the box style.
    Returns detected style, confidence, and suggestion if mismatch found.
    """
    return detect_box_style_from_polygon(
        req.polygon,
        req.image_width,
        req.image_height,
        req.declared_style
    )