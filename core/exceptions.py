from fastapi import HTTPException

class InvalidBoxStyleError(HTTPException):
    def __init__(self, style: str):
        super().__init__(
            status_code=400,
            detail=f"Unknown box style: '{style}'. Valid styles are: bottom_side_lock, straight_tuck_end, reverse_tuck_end, lock_bottom"
        )

class PDFExtractionError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=422,
            detail=f"PDF extraction failed: {message}"
        )

class InvalidDimensionsError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=400,
            detail=f"Invalid dimensions: {message}"
        )