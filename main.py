from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Mono Backend", version="1.0")

# Allow requests from your React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # We'll restrict this later
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── INPUT MODELS ──

class LayoutRequest(BaseModel):
    carton_w: float
    carton_h: float
    sheet_w: float
    sheet_h: float
    margin: float
    nesting_pct: float = 0  # Only used for tumble

# ── OUTPUT MODELS ──

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
    nesting_saving: float = 0
    pair_height: float = 0

# ── ALGORITHMS ──

def calc_straight(req: LayoutRequest) -> LayoutResponse:
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    per_row = int(usable_w // req.carton_w)
    num_rows = int(usable_h // req.carton_h)
    total = per_row * num_rows
    utilization = round((total * req.carton_w * req.carton_h) / (usable_w * usable_h) * 100, 2)

    cartons = []
    for row in range(num_rows):
        for col in range(per_row):
            x = req.margin + col * req.carton_w
            y = req.margin + row * req.carton_h
            cartons.append(CartonPosition(
                x=x, y=y,
                w=req.carton_w, h=req.carton_h,
                flipped=False,
                row=row, col=col
            ))

    return LayoutResponse(
        layout_type="straight",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=utilization,
        usable_w=usable_w,
        usable_h=usable_h,
        sheet_w=req.sheet_w,
        sheet_h=req.sheet_h,
        margin=req.margin,
    )


def calc_tumble(req: LayoutRequest) -> LayoutResponse:
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    per_row = int(usable_w // req.carton_w)
    nesting_saving = req.carton_h * (req.nesting_pct / 100)
    pair_height = req.carton_h * 2 - nesting_saving

    full_pairs = int(usable_h // pair_height)
    remaining_h = usable_h - full_pairs * pair_height
    extra_row = 1 if remaining_h >= req.carton_h else 0

    # Build row list with positions and orientations
    rows = []
    current_y = 0
    for i in range(full_pairs):
        rows.append({"y": current_y, "flipped": False})
        current_y += req.carton_h
        rows.append({"y": current_y - nesting_saving, "flipped": True})
        current_y += req.carton_h - nesting_saving
    if extra_row:
        rows.append({"y": current_y, "flipped": False})

    total = per_row * len(rows)
    utilization = round((total * req.carton_w * req.carton_h) / (usable_w * usable_h) * 100, 2)

    cartons = []
    for row_idx, row_data in enumerate(rows):
        for col in range(per_row):
            x = req.margin + col * req.carton_w
            y = req.margin + row_data["y"]
            cartons.append(CartonPosition(
                x=x, y=y,
                w=req.carton_w, h=req.carton_h,
                flipped=row_data["flipped"],
                row=row_idx, col=col
            ))

    return LayoutResponse(
        layout_type="tumble",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=len(rows),
        utilization=utilization,
        usable_w=usable_w,
        usable_h=usable_h,
        sheet_w=req.sheet_w,
        sheet_h=req.sheet_h,
        margin=req.margin,
        nesting_saving=round(nesting_saving, 2),
        pair_height=round(pair_height, 2),
    )


# ── ROUTES ──

@app.get("/")
def root():
    return {"message": "Mono Backend is running", "version": "1.0"}

@app.post("/layout/straight", response_model=LayoutResponse)
def straight_layout(req: LayoutRequest):
    return calc_straight(req)

@app.post("/layout/tumble", response_model=LayoutResponse)
def tumble_layout(req: LayoutRequest):
    return calc_tumble(req)