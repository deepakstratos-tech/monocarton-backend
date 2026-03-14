from pydantic import BaseModel
from typing import Optional

class CartonSpecRequest(BaseModel):
    style: str
    length: float
    width: float
    height: float
    custom_top_tuck: Optional[float] = None
    custom_bottom_tuck: Optional[float] = None
    custom_glue_flap: Optional[float] = None

class CartonSpecResponse(BaseModel):
    style: str
    style_name: str
    length: float
    width: float
    height: float
    flat_w: float
    flat_h: float
    top_tuck_depth: float
    bottom_tuck_depth: float
    glue_flap: float
    nesting_saving_mm: float
    nesting_saving_pct: float