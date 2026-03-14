from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Mono Backend", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── BOX STYLE DEFINITIONS ──

BOX_STYLES = {
    "bottom_side_lock": {
        "name": "Bottom Side Lock",
        "top_tuck_ratio": 0.40,
        "bottom_lock_ratio": 0.50,
        "glue_flap_mm": 10,
        "description": "Top tuck flap with interlocking bottom panels. Common in pharma."
    },
    "straight_tuck_end": {
        "name": "Straight Tuck End",
        "top_tuck_ratio": 0.35,
        "bottom_tuck_ratio": 0.35,
        "glue_flap_mm": 10,
        "description": "Both tuck flaps face same direction."
    },
    "reverse_tuck_end": {
        "name": "Reverse Tuck End",
        "top_tuck_ratio": 0.35,
        "bottom_tuck_ratio": 0.35,
        "glue_flap_mm": 10,
        "description": "Tuck flaps face opposite directions. Better nesting in tumble."
    },
    "lock_bottom": {
        "name": "Lock Bottom",
        "top_tuck_ratio": 0.40,
        "bottom_lock_ratio": 0.60,
        "glue_flap_mm": 10,
        "description": "Pre-glued auto locking bottom. Strong base for heavy products."
    },
}

# ── INPUT MODELS ──

class CartonSpecRequest(BaseModel):
    style: str
    length: float      # L in mm
    width: float       # W in mm
    height: float      # H in mm
    custom_top_tuck: Optional[float] = None    # override in mm
    custom_bottom_tuck: Optional[float] = None # override in mm
    custom_glue_flap: Optional[float] = None   # override in mm

class LayoutRequest(BaseModel):
    # Carton spec
    style: str
    length: float
    width: float
    height: float
    custom_top_tuck: Optional[float] = None
    custom_bottom_tuck: Optional[float] = None
    custom_glue_flap: Optional[float] = None
    nesting_pct_override: Optional[float] = None  # manual override

    # Sheet spec (all in mm)
    sheet_w: float
    sheet_h: float
    margin: float = 10.0  # default 10mm margin all sides

# ── OUTPUT MODELS ──

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

# ── FLAT SIZE CALCULATOR ──

def calculate_flat_size(req: CartonSpecRequest) -> CartonSpecResponse:
    style = BOX_STYLES.get(req.style)
    if not style:
        raise ValueError(f"Unknown box style: {req.style}")

    glue_flap = req.custom_glue_flap or style["glue_flap_mm"]
    top_tuck = req.custom_top_tuck or round(req.height * style["top_tuck_ratio"], 2)

    # Bottom depth depends on style
    if req.style in ["bottom_side_lock", "lock_bottom"]:
        bottom_depth = req.custom_bottom_tuck or round(
            req.height * style["bottom_lock_ratio"], 2
        )
    else:
        bottom_depth = req.custom_bottom_tuck or round(
            req.height * style["bottom_tuck_ratio"], 2
        )

    flat_w = round(2 * (req.length + req.width) + glue_flap, 2)
    flat_h = round(req.height + top_tuck + bottom_depth, 2)

    # Nesting saving = top tuck depth (the part that nests in tumble layout)
    nesting_saving_mm = top_tuck
    nesting_saving_pct = round((nesting_saving_mm / flat_h) * 100, 2)

    return CartonSpecResponse(
        style=req.style,
        style_name=style["name"],
        length=req.length,
        width=req.width,
        height=req.height,
        flat_w=flat_w,
        flat_h=flat_h,
        top_tuck_depth=top_tuck,
        bottom_tuck_depth=bottom_depth,
        glue_flap=glue_flap,
        nesting_saving_mm=nesting_saving_mm,
        nesting_saving_pct=nesting_saving_pct,
    )

# ── HELPER ──

def calc_utilization(total, cw, ch, uw, uh):
    return round((total * cw * ch) / (uw * uh) * 100, 2)

def get_carton_dims(req: LayoutRequest):
    spec = calculate_flat_size(CartonSpecRequest(
        style=req.style,
        length=req.length,
        width=req.width,
        height=req.height,
        custom_top_tuck=req.custom_top_tuck,
        custom_bottom_tuck=req.custom_bottom_tuck,
        custom_glue_flap=req.custom_glue_flap,
    ))
    nesting_pct = req.nesting_pct_override if req.nesting_pct_override is not None \
        else spec.nesting_saving_pct
    return spec.flat_w, spec.flat_h, nesting_pct, spec.nesting_saving_mm

# ── ALGORITHM 1: STRAIGHT ──

def calc_straight(req: LayoutRequest) -> LayoutResponse:
    flat_w, flat_h, nesting_pct, nesting_mm = get_carton_dims(req)
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2
    per_row = int(usable_w // flat_w)
    num_rows = int(usable_h // flat_h)
    total = per_row * num_rows

    cartons = []
    for row in range(num_rows):
        for col in range(per_row):
            cartons.append(CartonPosition(
                x=req.margin + col * flat_w,
                y=req.margin + row * flat_h,
                w=flat_w, h=flat_h,
                flipped=False, row=row, col=col
            ))

    return LayoutResponse(
        layout_type="straight",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, flat_w, flat_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        flat_w=flat_w, flat_h=flat_h,
        nesting_saving_mm=nesting_mm,
        nesting_saving_pct=nesting_pct,
        algorithm_notes="Simple row by row placement. All cartons same direction."
    )

# ── ALGORITHM 2: TUMBLE ──

def calc_tumble(req: LayoutRequest) -> LayoutResponse:
    flat_w, flat_h, nesting_pct, nesting_mm = get_carton_dims(req)
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2
    per_row = int(usable_w // flat_w)

    nesting_saving = flat_h * (nesting_pct / 100)
    pair_height = flat_h * 2 - nesting_saving
    full_pairs = int(usable_h // pair_height)
    remaining_h = usable_h - full_pairs * pair_height
    extra_row = 1 if remaining_h >= flat_h else 0

    rows = []
    current_y = 0
    for i in range(full_pairs):
        rows.append({"y": current_y, "flipped": False})
        current_y += flat_h
        rows.append({"y": current_y - nesting_saving, "flipped": True})
        current_y += flat_h - nesting_saving
    if extra_row:
        rows.append({"y": current_y, "flipped": False})

    total = per_row * len(rows)
    cartons = []
    for row_idx, row_data in enumerate(rows):
        for col in range(per_row):
            cartons.append(CartonPosition(
                x=req.margin + col * flat_w,
                y=req.margin + row_data["y"],
                w=flat_w, h=flat_h,
                flipped=row_data["flipped"],
                row=row_idx, col=col
            ))

    return LayoutResponse(
        layout_type="tumble",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=len(rows),
        utilization=calc_utilization(total, flat_w, flat_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        flat_w=flat_w, flat_h=flat_h,
        nesting_saving_mm=round(nesting_saving, 2),
        nesting_saving_pct=nesting_pct,
        pair_height=round(pair_height, 2),
        algorithm_notes="Alternate rows flipped 180°. Nesting saving applied between row pairs."
    )

# ── ALGORITHM 3: FIRST FIT ──

def calc_first_fit(req: LayoutRequest) -> LayoutResponse:
    flat_w, flat_h, nesting_pct, nesting_mm = get_carton_dims(req)
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2
    per_row = int(usable_w // flat_w)
    num_rows = int(usable_h // flat_h)
    total = per_row * num_rows

    cartons = []
    for row in range(num_rows):
        for col in range(per_row):
            cartons.append(CartonPosition(
                x=req.margin + col * flat_w,
                y=req.margin + row * flat_h,
                w=flat_w, h=flat_h,
                flipped=False, row=row, col=col
            ))

    return LayoutResponse(
        layout_type="first_fit",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, flat_w, flat_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        flat_w=flat_w, flat_h=flat_h,
        nesting_saving_mm=nesting_mm,
        nesting_saving_pct=nesting_pct,
        algorithm_notes="First Fit: places each carton in first available position."
    )

# ── ALGORITHM 4: FIRST FIT DECREASING ──

def calc_first_fit_decreasing(req: LayoutRequest) -> LayoutResponse:
    flat_w, flat_h, nesting_pct, nesting_mm = get_carton_dims(req)
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    per_row_normal = int(usable_w // flat_w)
    num_rows_normal = int(usable_h // flat_h)
    total_normal = per_row_normal * num_rows_normal

    per_row_rotated = int(usable_w // flat_h)
    num_rows_rotated = int(usable_h // flat_w)
    total_rotated = per_row_rotated * num_rows_rotated

    if total_rotated > total_normal:
        per_row, num_rows, cw, ch = per_row_rotated, num_rows_rotated, flat_h, flat_w
        note = "FFD: Rotated carton 90° for better fit."
    else:
        per_row, num_rows, cw, ch = per_row_normal, num_rows_normal, flat_w, flat_h
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
        flat_w=flat_w, flat_h=flat_h,
        nesting_saving_mm=nesting_mm,
        nesting_saving_pct=nesting_pct,
        algorithm_notes=note
    )

# ── ALGORITHM 5: NFDH ──

def calc_nfdh(req: LayoutRequest) -> LayoutResponse:
    flat_w, flat_h, nesting_pct, nesting_mm = get_carton_dims(req)
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    cartons = []
    current_x = 0
    current_y = 0
    shelf_height = flat_h
    row_idx = 0
    col_idx = 0

    while current_y + flat_h <= usable_h:
        if current_x + flat_w <= usable_w:
            cartons.append(CartonPosition(
                x=req.margin + current_x,
                y=req.margin + current_y,
                w=flat_w, h=flat_h,
                flipped=False, row=row_idx, col=col_idx
            ))
            current_x += flat_w
            col_idx += 1
        else:
            current_y += shelf_height
            current_x = 0
            col_idx = 0
            row_idx += 1
            shelf_height = flat_h
            if current_y + flat_h > usable_h:
                break
            cartons.append(CartonPosition(
                x=req.margin + current_x,
                y=req.margin + current_y,
                w=flat_w, h=flat_h,
                flipped=False, row=row_idx, col=col_idx
            ))
            current_x += flat_w
            col_idx += 1

    total = len(cartons)
    per_row = int(usable_w // flat_w)
    num_rows = row_idx + 1 if cartons else 0

    return LayoutResponse(
        layout_type="nfdh",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, flat_w, flat_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        flat_w=flat_w, flat_h=flat_h,
        nesting_saving_mm=nesting_mm,
        nesting_saving_pct=nesting_pct,
        algorithm_notes="NFDH: Shelf based packing sorted by height."
    )

# ── ALGORITHM 6: BEST FIT ──

def calc_best_fit(req: LayoutRequest) -> LayoutResponse:
    flat_w, flat_h, nesting_pct, nesting_mm = get_carton_dims(req)
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    shelves = []
    cartons = []
    per_row = int(usable_w // flat_w)
    num_rows = int(usable_h // flat_h)
    total_needed = per_row * num_rows

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

    for i in range(total_needed):
        shelf = find_best_shelf(flat_w, flat_h)
        if shelf:
            x = shelf["next_x"]
            y = shelf["y"]
            col = int(x / flat_w)
            cartons.append(CartonPosition(
                x=req.margin + x, y=req.margin + y,
                w=flat_w, h=flat_h,
                flipped=False, row=shelf["row"], col=col
            ))
            shelf["next_x"] += flat_w
        else:
            new_y = len(shelves) * flat_h
            if new_y + flat_h > usable_h:
                break
            new_shelf = {"y": new_y, "next_x": flat_w, "height": flat_h, "row": len(shelves)}
            shelves.append(new_shelf)
            cartons.append(CartonPosition(
                x=req.margin + 0, y=req.margin + new_y,
                w=flat_w, h=flat_h,
                flipped=False, row=new_shelf["row"], col=0
            ))

    total = len(cartons)
    return LayoutResponse(
        layout_type="best_fit",
        cartons=cartons,
        total_cartons=total,
        cartons_per_row=per_row,
        num_rows=num_rows,
        utilization=calc_utilization(total, flat_w, flat_h, usable_w, usable_h),
        usable_w=usable_w, usable_h=usable_h,
        sheet_w=req.sheet_w, sheet_h=req.sheet_h,
        margin=req.margin,
        flat_w=flat_w, flat_h=flat_h,
        nesting_saving_mm=nesting_mm,
        nesting_saving_pct=nesting_pct,
        algorithm_notes="Best Fit: places carton in shelf with least remaining space."
    )

# ── COMPARE ──

@app.post("/layout/compare")
def compare_layouts(req: LayoutRequest):
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
    comparison.sort(key=lambda x: x["total_cartons"], reverse=True)
    return {
        "best_algorithm": comparison[0]["algorithm"],
        "best_total": comparison[0]["total_cartons"],
        "flat_w": results["straight"].flat_w,
        "flat_h": results["straight"].flat_h,
        "nesting_saving_mm": results["straight"].nesting_saving_mm,
        "nesting_saving_pct": results["straight"].nesting_saving_pct,
        "comparison": comparison
    }

# ── ROUTES ──

@app.get("/")
def root():
    return {"message": "Mono Backend is running", "version": "2.0"}

@app.get("/box-styles")
def get_box_styles():
    return {k: {"name": v["name"], "description": v["description"]} for k, v in BOX_STYLES.items()}

@app.post("/carton/flat-size", response_model=CartonSpecResponse)
def get_flat_size(req: CartonSpecRequest):
    try:
        return calculate_flat_size(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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