from pydantic import BaseModel
from typing import List, Optional

class LayoutRequest(BaseModel):
    style: str
    length: float
    width: float
    height: float
    custom_top_tuck: Optional[float] = None
    custom_bottom_tuck: Optional[float] = None
    custom_glue_flap: Optional[float] = None
    nesting_pct_override: Optional[float] = None
    sheet_w: float
    sheet_h: float
    margin: float = 10.0

class CartonPosition(BaseModel):
    x: float
    y: float
    w: float
    h: float
    flipped: bool
    row: int
    col: int

class LayoutResponse(BaseModel):
    layout_type: str
    cartons: List[CartonPosition]
    total_cartons: int
    cartons_per_row: int
    num_rows: int
    utilization: float
    usable_w: float
    usable_h: float
    sheet_w: float
    sheet_h: float
    margin: float
    flat_w: float
    flat_h: float
    nesting_saving_mm: float
    nesting_saving_pct: float
    pair_height: float = 0
    algorithm_notes: str = ""