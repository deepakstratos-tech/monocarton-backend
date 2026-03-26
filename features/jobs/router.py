from fastapi import APIRouter
from features.jobs.models import (
    JobSpec, JobSpecResponse, SheetPlanRequest,
    CompatibilityResult, MultiSKULayoutResponse,
    AlignmentAnalysisResponse
)
from features.jobs.service import (
    enrich_job, check_compatibility,
    calculate_multi_sku_layout, analyse_impression_alignment
)
from typing import List

router = APIRouter()

@router.post("/enrich", response_model=List[JobSpecResponse])
def enrich_jobs(jobs: List[JobSpec]):
    """
    Enrich job specs with calculated flat sizes.
    Call this after entering job dimensions to get flat size preview.
    """
    return [enrich_job(job, idx) for idx, job in enumerate(jobs)]

@router.post("/check-compatibility", response_model=CompatibilityResult)
def check_jobs_compatibility(req: SheetPlanRequest):
    """
    Check if a list of jobs are compatible for gang printing.
    Returns compatible groups and any hard/soft constraint issues.
    """
    return check_compatibility(req)

@router.post("/analyse-alignment", response_model=AlignmentAnalysisResponse)
def analyse_alignment(req: SheetPlanRequest):
    """
    Analyse impression alignment options for a set of compatible jobs.
    Returns top 10 carton count combinations ranked by alignment score.
    Use this to find the layout that guarantees color consistency.
    """
    return analyse_impression_alignment(req)

@router.post("/multi-sku-layout", response_model=MultiSKULayoutResponse)
def multi_sku_layout(req: SheetPlanRequest):
    """
    Calculate the optimal multi-SKU layout for a set of compatible jobs.
    Uses impression alignment to ensure color consistency across all jobs.
    """
    return calculate_multi_sku_layout(req)
