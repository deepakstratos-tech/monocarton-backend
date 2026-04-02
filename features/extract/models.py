from pydantic import BaseModel
from typing import List, Optional

class Point(BaseModel):
    x: float
    y: float

class ConvertResponse(BaseModel):
    success: bool
    image_base64: str = ""
    width: int = 0
    height: int = 0
    pages: int = 1
    notes: str = ""

class CropRequest(BaseModel):
    image_base64: str           # original full page image
    polygon: List[Point]        # polygon points in image coordinates
    job_id: Optional[str] = ""

class DesignAsset(BaseModel):
    success: bool
    job_id: str = ""
    cropped_image_base64: str = ""   # cropped polygon region
    mask_image_base64: str = ""      # polygon mask for nesting
    polygon: List[Point] = []        # original polygon points
    bounding_box: dict = {}          # x, y, w, h of bounding box
    width: int = 0
    height: int = 0
    notes: str = ""
    
class BoxStyleDetectionRequest(BaseModel):
    polygon: List[Point]
    image_width: int
    image_height: int
    declared_style: str  # what user selected

class BoxStyleDetectionResult(BaseModel):
    detected_style: str
    detected_style_name: str
    declared_style: str
    declared_style_name: str
    confidence: str          # High / Medium / Low
    match: bool              # True if detected == declared
    suggestion: str          # message to show user
    top_ratio: float         # top flap / total height
    bottom_ratio: float      # bottom flap / total height
    analysis_notes: str