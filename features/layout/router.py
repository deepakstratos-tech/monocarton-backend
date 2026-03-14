from fastapi import APIRouter
from features.layout.models import LayoutRequest, LayoutResponse
from features.layout.algorithms import (
    calc_straight, calc_tumble, calc_first_fit,
    calc_first_fit_decreasing, calc_nfdh, calc_best_fit, compare_all
)

router = APIRouter()

@router.post("/straight", response_model=LayoutResponse)
def straight_layout(req: LayoutRequest):
    return calc_straight(req)

@router.post("/tumble", response_model=LayoutResponse)
def tumble_layout(req: LayoutRequest):
    return calc_tumble(req)

@router.post("/first-fit", response_model=LayoutResponse)
def first_fit_layout(req: LayoutRequest):
    return calc_first_fit(req)

@router.post("/first-fit-decreasing", response_model=LayoutResponse)
def first_fit_decreasing_layout(req: LayoutRequest):
    return calc_first_fit_decreasing(req)

@router.post("/nfdh", response_model=LayoutResponse)
def nfdh_layout(req: LayoutRequest):
    return calc_nfdh(req)

@router.post("/best-fit", response_model=LayoutResponse)
def best_fit_layout(req: LayoutRequest):
    return calc_best_fit(req)

@router.post("/compare")
def compare_layouts(req: LayoutRequest):
    return compare_all(req)