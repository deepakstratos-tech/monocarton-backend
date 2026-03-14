from features.cartons.models import CartonSpecRequest, CartonSpecResponse
from core.exceptions import InvalidBoxStyleError

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

def get_all_styles():
    return {k: {"name": v["name"], "description": v["description"]} for k, v in BOX_STYLES.items()}

def calculate_flat_size(req: CartonSpecRequest) -> CartonSpecResponse:
    style = BOX_STYLES.get(req.style)
    if not style:
        raise InvalidBoxStyleError(req.style)

    glue_flap = req.custom_glue_flap or style["glue_flap_mm"]
    top_tuck = req.custom_top_tuck or round(req.height * style["top_tuck_ratio"], 2)

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