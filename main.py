from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Mono Backend", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    nesting_pct: float = 0

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
    algorithm_notes: str = ""

# ── HELPER ──

def calc_utilization(total, cw, ch, uw, uh):
    return round((total * cw * ch) / (uw * uh) * 100, 2)

# ── ALGORITHM 1: STRAIGHT LAYOUT ──

def calc_straight(req: LayoutRequest) -> LayoutResponse:
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2
    per_row = int(usable_w // req.carton_w)
    num_rows = int(usable_h // req.carton_h)
    total = per_row * num_rows

    cartons = []
    for row in range(num_rows):
        for col in range(per_row):
            cartons.append(CartonPosition(
                x=req.margin + col * req.carton_w,
                y=req.margin + row * req.carton_h,
                w=req.carton_w, h=req.carton_h,
                flipped=False, row=row, col=col
            ))

    return LayoutResponse(
        layout_type="straight",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, req.carton_w, req.carton_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        algorithm_notes="Simple row by row placement. All cartons same direction."
    )

# ── ALGORITHM 2: TUMBLE LAYOUT ──

def calc_tumble(req: LayoutRequest) -> LayoutResponse:
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2
    per_row = int(usable_w // req.carton_w)
    nesting_saving = req.carton_h * (req.nesting_pct / 100)
    pair_height = req.carton_h * 2 - nesting_saving

    full_pairs = int(usable_h // pair_height)
    remaining_h = usable_h - full_pairs * pair_height
    extra_row = 1 if remaining_h >= req.carton_h else 0

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
    cartons = []
    for row_idx, row_data in enumerate(rows):
        for col in range(per_row):
            cartons.append(CartonPosition(
                x=req.margin + col * req.carton_w,
                y=req.margin + row_data["y"],
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
        utilization=calc_utilization(total, req.carton_w, req.carton_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        nesting_saving=round(nesting_saving, 2),
        pair_height=round(pair_height, 2),
        algorithm_notes="Alternate rows flipped 180 degrees. Nesting saving applied between row pairs."
    )

# ── ALGORITHM 3: FIRST FIT (FF) ──

def calc_first_fit(req: LayoutRequest) -> LayoutResponse:
    """
    Place each carton into the first available position on the sheet
    scanning left to right, top to bottom.
    No sorting — cartons placed in natural order.
    """
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    cartons = []
    # Track occupied spaces as a grid with fine resolution
    # We use a shelf-based approach for efficiency
    shelves = []  # Each shelf: {"y": float, "next_x": float, "height": float}
    row_idx = 0

    def try_place(cw, ch):
        # Try to place in an existing shelf
        for shelf in shelves:
            if shelf["next_x"] + cw <= usable_w and shelf["y"] + ch <= usable_h:
                x = shelf["next_x"]
                y = shelf["y"]
                shelf["next_x"] += cw
                return x, y
        # Start a new shelf
        new_y = sum(s["height"] for s in shelves)
        if new_y + ch <= usable_h:
            shelves.append({"y": new_y, "next_x": cw, "height": ch})
            return 0, new_y
        return None, None

    col_idx = 0
    current_row = 0
    placed = 0

    # Simple grid placement (First Fit without sorting)
    per_row = int(usable_w // req.carton_w)
    num_rows = int(usable_h // req.carton_h)

    for row in range(num_rows):
        for col in range(per_row):
            x = col * req.carton_w
            y = row * req.carton_h
            cartons.append(CartonPosition(
                x=req.margin + x,
                y=req.margin + y,
                w=req.carton_w, h=req.carton_h,
                flipped=False, row=row, col=col
            ))

    total = len(cartons)
    return LayoutResponse(
        layout_type="first_fit",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, req.carton_w, req.carton_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        algorithm_notes="First Fit: places each carton in first available position, left to right top to bottom."
    )

# ── ALGORITHM 4: FIRST FIT DECREASING (FFD) ──

def calc_first_fit_decreasing(req: LayoutRequest) -> LayoutResponse:
    """
    Sort cartons largest first (by area), then apply First Fit.
    For identical cartons this behaves same as straight layout,
    but becomes powerful when multiple carton sizes are involved.
    Currently handles single carton size — foundation for multi-SKU later.
    """
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    # For single carton size, try both orientations and pick the better one
    # Orientation 1: normal (w x h)
    per_row_normal = int(usable_w // req.carton_w)
    num_rows_normal = int(usable_h // req.carton_h)
    total_normal = per_row_normal * num_rows_normal

    # Orientation 2: rotated (h x w)
    per_row_rotated = int(usable_w // req.carton_h)
    num_rows_rotated = int(usable_h // req.carton_w)
    total_rotated = per_row_rotated * num_rows_rotated

    # Pick best orientation
    if total_rotated > total_normal:
        per_row = per_row_rotated
        num_rows = num_rows_rotated
        cw = req.carton_h
        ch = req.carton_w
        note = "FFD: Rotated carton 90° for better fit."
    else:
        per_row = per_row_normal
        num_rows = num_rows_normal
        cw = req.carton_w
        ch = req.carton_h
        note = "FFD: Normal orientation gives best fit."

    cartons = []
    for row in range(num_rows):
        for col in range(per_row):
            cartons.append(CartonPosition(
                x=req.margin + col * cw,
                y=req.margin + row * ch,
                w=cw, h=ch,
                flipped=False, row=row, col=col
            ))

    total = len(cartons)
    return LayoutResponse(
        layout_type="first_fit_decreasing",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, cw, ch, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        algorithm_notes=note
    )

# ── ALGORITHM 5: NEXT FIT DECREASING HEIGHT (NFDH) ──

def calc_nfdh(req: LayoutRequest) -> LayoutResponse:
    """
    NFDH - Next Fit Decreasing Height:
    1. Sort cartons by height tallest first
    2. Pack into horizontal shelves
    3. Each shelf height = tallest carton in that shelf
    4. When carton doesn't fit in current shelf width, start new shelf
    5. When new shelf doesn't fit in remaining height, stop

    For single carton size this is equivalent to straight layout,
    but the shelf structure gives better results with mixed sizes.
    This is the foundation for multi-SKU support in Mono.
    """
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    cartons = []
    current_x = 0
    current_y = 0
    shelf_height = req.carton_h  # Height of current shelf
    row_idx = 0
    col_idx = 0

    while current_y + req.carton_h <= usable_h:
        # Try to place carton in current shelf
        if current_x + req.carton_w <= usable_w:
            cartons.append(CartonPosition(
                x=req.margin + current_x,
                y=req.margin + current_y,
                w=req.carton_w, h=req.carton_h,
                flipped=False, row=row_idx, col=col_idx
            ))
            current_x += req.carton_w
            col_idx += 1
        else:
            # Start new shelf
            current_y += shelf_height
            current_x = 0
            col_idx = 0
            row_idx += 1
            shelf_height = req.carton_h

            # Check if new shelf fits
            if current_y + req.carton_h > usable_h:
                break

            # Place carton in new shelf
            cartons.append(CartonPosition(
                x=req.margin + current_x,
                y=req.margin + current_y,
                w=req.carton_w, h=req.carton_h,
                flipped=False, row=row_idx, col=col_idx
            ))
            current_x += req.carton_w
            col_idx += 1

    total = len(cartons)
    per_row = int(usable_w // req.carton_w)
    num_rows = row_idx + 1 if cartons else 0

    return LayoutResponse(
        layout_type="nfdh",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, req.carton_w, req.carton_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        algorithm_notes="NFDH: Packs cartons into shelves sorted by height. Best for mixed carton sizes."
    )

# ── ALGORITHM 6: BEST FIT (BF) ──

def calc_best_fit(req: LayoutRequest) -> LayoutResponse:
    """
    Best Fit:
    For each carton, find the shelf with least remaining width
    that still fits the carton. This minimises wasted space per shelf.
    More efficient than First Fit but slightly slower to compute.
    """
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    shelves = []  # Each shelf: {"y": float, "next_x": float, "height": float, "row": int}
    cartons = []
    total_placed = 0

    def find_best_shelf(cw, ch):
        best = None
        best_remaining = float("inf")
        for shelf in shelves:
            remaining = usable_w - shelf["next_x"]
            if remaining >= cw and shelf["y"] + ch <= usable_h:
                if remaining < best_remaining:
                    best_remaining = remaining
                    best = shelf
        return best

    # Calculate how many cartons we need to place
    per_row = int(usable_w // req.carton_w)
    num_rows = int(usable_h // req.carton_h)
    total_cartons_needed = per_row * num_rows

    for i in range(total_cartons_needed):
        shelf = find_best_shelf(req.carton_w, req.carton_h)

        if shelf:
            x = shelf["next_x"]
            y = shelf["y"]
            col = int(x / req.carton_w)
            cartons.append(CartonPosition(
                x=req.margin + x,
                y=req.margin + y,
                w=req.carton_w, h=req.carton_h,
                flipped=False, row=shelf["row"], col=col
            ))
            shelf["next_x"] += req.carton_w
        else:
            # Open new shelf
            new_y = len(shelves) * req.carton_h
            if new_y + req.carton_h > usable_h:
                break
            new_shelf = {
                "y": new_y,
                "next_x": req.carton_w,
                "height": req.carton_h,
                "row": len(shelves)
            }
            shelves.append(new_shelf)
            cartons.append(CartonPosition(
                x=req.margin + 0,
                y=req.margin + new_y,
                w=req.carton_w, h=req.carton_h,
                flipped=False, row=new_shelf["row"], col=0
            ))

    total = len(cartons)
    return LayoutResponse(
        layout_type="best_fit",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, req.carton_w, req.carton_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        algorithm_notes="Best Fit: places each carton in shelf with least remaining space. Minimises waste per shelf."
    )

# ── COMPARISON ENDPOINT ──

@app.post("/layout/compare")
def compare_layouts(req: LayoutRequest):
    """
    Run all algorithms and return a comparison summary.
    Useful for finding which algorithm gives best yield for a given job.
    """
    results = {
        "straight": calc_straight(req),
        "tumble": calc_tumble(req),
        "first_fit": calc_first_fit(req),
        "first_fit_decreasing": calc_first_fit_decreasing(req),
        "nfdh": calc_nfdh(req),
        "best_fit": calc_best_fit(req),
    }

    comparison = []
    for algo, result in results.items():
        comparison.append({
            "algorithm": algo,
            "total_cartons": result.total_cartons,
            "utilization": result.utilization,
            "cartons_per_row": result.cartons_per_row,
            "num_rows": result.num_rows,
            "notes": result.algorithm_notes
        })

    # Sort by total cartons descending
    comparison.sort(key=lambda x: x["total_cartons"], reverse=True)

    return {
        "best_algorithm": comparison[0]["algorithm"],
        "best_total": comparison[0]["total_cartons"],
        "comparison": comparison
    }

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

@app.post("/layout/first-fit", response_model=LayoutResponse)
def first_fit_layout(req: LayoutRequest):
    return calc_first_fit(req)

@app.post("/layout/first-fit-decreasing", response_model=LayoutResponse)
def first_fit_decreasing_layout(req: LayoutRequest):
    return calc_first_fit_decreasing(req)

@app.post("/layout/nfdh", response_model=LayoutResponse)
def nfdh_layout(req: LayoutRequest):
    return calc_nfdh(req)

@app.post("/layout/best-fit", response_model=LayoutResponse)
def best_fit_layout(req: LayoutRequest):
    return calc_best_fit(req)