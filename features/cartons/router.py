from fastapi import APIRouter
from features.cartons.models import CartonSpecRequest, CartonSpecResponse
from features.cartons.service import calculate_flat_size, get_all_styles

router = APIRouter()

@router.get("/styles")
def box_styles():
    return get_all_styles()

@router.post("/flat-size", response_model=CartonSpecResponse)
def flat_size(req: CartonSpecRequest):
    return calculate_flat_size(req)