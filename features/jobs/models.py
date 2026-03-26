from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import uuid

# ── ENUMS ──

class PaperType(str, Enum):
    FBB = "FBB"
    SBS = "SBS"
    ITC_SAFIRE = "ITC_SAFIRE"
    ART_CARD = "ART_CARD"
    DUPLEX = "DUPLEX"

class Lamination(str, Enum):
    NONE = "NONE"
    GLOSS = "GLOSS"
    MATT = "MATT"
    SOFT_TOUCH = "SOFT_TOUCH"
    UV = "UV"
    ANTI_SCRATCH = "ANTI_SCRATCH"

class Colours(str, Enum):
    CMYK = "CMYK"
    CMYK_1P = "CMYK_1P"       # CMYK + 1 Pantone
    CMYK_2P = "CMYK_2P"       # CMYK + 2 Pantone
    CMYK_3P = "CMYK_3P"       # CMYK + 3 Pantone

class Stamping(str, Enum):
    NONE = "NONE"
    FOIL = "FOIL"
    EMBOSS = "EMBOSS"
    FOIL_EMBOSS = "FOIL_EMBOSS"

class BoxStyle(str, Enum):
    BOTTOM_SIDE_LOCK = "bottom_side_lock"
    STRAIGHT_TUCK_END = "straight_tuck_end"
    REVERSE_TUCK_END = "reverse_tuck_end"
    LOCK_BOTTOM = "lock_bottom"

# ── JOB SPEC ──

class JobSpec(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    client_name: str
    product_name: str
    style: BoxStyle
    length: float
    width: float
    height: float
    quantity: int
    paper_type: PaperType
    gsm: float
    lamination: Lamination
    colours: Colours
    stamping: Stamping = Stamping.NONE

class JobSpecResponse(JobSpec):
    flat_w: float = 0
    flat_h: float = 0
    top_tuck_depth: float = 0
    nesting_saving_pct: float = 0

# ── SHEET PLAN REQUEST ──

class SheetPlanRequest(BaseModel):
    jobs: List[JobSpec]
    sheet_w: float
    sheet_h: float
    margin: float = 10.0
    overrun_tolerance_pct: float = 5.0  # acceptable overrun %
    gsm_tolerance: float = 10.0         # acceptable GSM difference

# ── COMPATIBILITY ──

class CompatibilityIssue(BaseModel):
    job_id_a: str
    job_id_b: str
    issue_type: str    # HARD or SOFT
    field: str
    value_a: str
    value_b: str
    message: str

class CompatibilityResult(BaseModel):
    compatible: bool
    groups: List[List[str]]   # list of compatible job_id groups
    issues: List[CompatibilityIssue]
    notes: List[str]

# ── MULTI-SKU LAYOUT ──

class JobLayoutSummary(BaseModel):
    job_id: str
    client_name: str
    product_name: str
    cartons_per_sheet: int
    impressions_needed: int
    actual_printed: int
    overrun_pct: float
    flat_w: float
    flat_h: float
    color: str   # hex color for canvas rendering

class MultiSKUCartonPosition(BaseModel):
    job_id: str
    product_name: str
    x: float
    y: float
    w: float
    h: float
    flipped: bool
    row: int
    col: int
    color: str

class MultiSKULayoutResponse(BaseModel):
    sheet_w: float
    sheet_h: float
    margin: float
    total_cartons_per_sheet: int
    utilization: float
    target_impressions: int
    impression_alignment_score: float   # 0-1, 1 = perfect
    overrun_warning: bool
    jobs_summary: List[JobLayoutSummary]
    cartons: List[MultiSKUCartonPosition]
    layout_notes: List[str]

# ── IMPRESSION ALIGNMENT ──

class AlignmentOption(BaseModel):
    cartons_per_job: dict           # job_id -> cartons per sheet
    impressions_per_job: dict       # job_id -> impressions needed
    target_impressions: int
    alignment_score: float
    max_overrun_pct: float
    total_cartons_per_sheet: int
    utilization: float

class AlignmentAnalysisResponse(BaseModel):
    sheet_w: float
    sheet_h: float
    best_option: AlignmentOption
    all_options: List[AlignmentOption]
    recommendation: str
