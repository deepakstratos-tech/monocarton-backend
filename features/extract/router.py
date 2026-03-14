from fastapi import APIRouter, UploadFile, File
from features.extract.service import ExtractedDimensions, extract_from_pdf

router = APIRouter()

@router.post("/pdf", response_model=ExtractedDimensions)
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        return ExtractedDimensions(
            success=False,
            notes="Please upload a PDF file."
        )
    file_bytes = await file.read()
    return extract_from_pdf(file_bytes)