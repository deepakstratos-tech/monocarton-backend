from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from features.extract.service import ExtractedDimensions, extract_from_pdf
from features.extract.models import CropRequest, ConvertResponse, DesignAsset
from features.extract.image_service import convert_file_to_image, crop_polygon_design

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
