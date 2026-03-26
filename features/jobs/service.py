import math
import itertools
from typing import List, Tuple, Dict
from features.jobs.models import (
    JobSpec, JobSpecResponse, SheetPlanRequest,
    CompatibilityResult, CompatibilityIssue,
    MultiSKULayoutResponse, MultiSKUCartonPosition,
    JobLayoutSummary, AlignmentOption, AlignmentAnalysisResponse
)
from features.cartons.models import CartonSpecRequest
from features.cartons.service import calculate_flat_size

# ── JOB COLORS for canvas rendering ──
JOB_COLORS = [
    "#4F86C6",  # Blue
    "#e67e22",  # Orange
    "#27ae60",  # Green
    "#9b59b6",  # Purple
    "#e74c3c",  # Red
    "#1abc9c",  # Teal
    "#f39c12",  # Yellow
    "#2c3e50",  # Dark blue
]

def get_job_color(index: int) -> str:
    return JOB_COLORS[index % len(JOB_COLORS)]

# ── FLAT SIZE FOR JOB ──

def get_flat_size_for_job(job: JobSpec) -> Tuple[float, float, float, float]:
    """Returns flat_w, flat_h, top_tuck_depth, nesting_saving_pct"""
    spec = calculate_flat_size(CartonSpecRequest(
        style=job.style.value,
        length=job.length,
        width=job.width,
        height=job.height,
    ))
    return spec.flat_w, spec.flat_h, spec.top_tuck_depth, spec.nesting_saving_pct

def enrich_job(job: JobSpec, index: int) -> JobSpecResponse:
    flat_w, flat_h, top_tuck, nesting_pct = get_flat_size_for_job(job)
    return JobSpecResponse(
        **job.model_dump(),
        flat_w=flat_w,
        flat_h=flat_h,
        top_tuck_depth=top_tuck,
        nesting_saving_pct=nesting_pct,
    )

# ── COMPATIBILITY CHECKER ──

def check_compatibility(req: SheetPlanRequest) -> CompatibilityResult:
    jobs = req.jobs
    issues = []
    notes = []

    # Build compatibility matrix
    # compatible_pairs[i][j] = True if jobs i and j can be combined
    n = len(jobs)
    compatible_matrix = [[True] * n for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            a = jobs[i]
            b = jobs[j]

            # Check 1: Paper Type (HARD)
            if a.paper_type != b.paper_type:
                compatible_matrix[i][j] = False
                compatible_matrix[j][i] = False
                issues.append(CompatibilityIssue(
                    job_id_a=a.job_id,
                    job_id_b=b.job_id,
                    issue_type="HARD",
                    field="paper_type",
                    value_a=a.paper_type.value,
                    value_b=b.paper_type.value,
                    message=f"Paper type mismatch: {a.paper_type.value} vs {b.paper_type.value}. Cannot combine on same sheet."
                ))

            # Check 2: GSM (HARD within tolerance)
            elif abs(a.gsm - b.gsm) > req.gsm_tolerance:
                compatible_matrix[i][j] = False
                compatible_matrix[j][i] = False
                issues.append(CompatibilityIssue(
                    job_id_a=a.job_id,
                    job_id_b=b.job_id,
                    issue_type="HARD",
                    field="gsm",
                    value_a=str(a.gsm),
                    value_b=str(b.gsm),
                    message=f"GSM difference too large: {a.gsm} vs {b.gsm} (tolerance: ±{req.gsm_tolerance}gsm)."
                ))

            # Check 3: Lamination (HARD)
            elif a.lamination != b.lamination:
                compatible_matrix[i][j] = False
                compatible_matrix[j][i] = False
                issues.append(CompatibilityIssue(
                    job_id_a=a.job_id,
                    job_id_b=b.job_id,
                    issue_type="HARD",
                    field="lamination",
                    value_a=a.lamination.value,
                    value_b=b.lamination.value,
                    message=f"Lamination mismatch: {a.lamination.value} vs {b.lamination.value}. Cannot combine on same sheet."
                ))

            # Soft warnings
            if a.colours != b.colours:
                issues.append(CompatibilityIssue(
                    job_id_a=a.job_id,
                    job_id_b=b.job_id,
                    issue_type="SOFT",
                    field="colours",
                    value_a=a.colours.value,
                    value_b=b.colours.value,
                    message=f"Colour difference: {a.colours.value} vs {b.colours.value}. Verify press can handle both."
                ))

            if a.stamping != b.stamping:
                issues.append(CompatibilityIssue(
                    job_id_a=a.job_id,
                    job_id_b=b.job_id,
                    issue_type="SOFT",
                    field="stamping",
                    value_a=a.stamping.value,
                    value_b=b.stamping.value,
                    message=f"Stamping difference: {a.stamping.value} vs {b.stamping.value}. Separate finishing pass may be needed."
                ))

    # Find compatible groups using union-find
    groups = find_compatible_groups(jobs, compatible_matrix)

    hard_issues = [i for i in issues if i.issue_type == "HARD"]
    all_compatible = len(hard_issues) == 0

    if all_compatible:
        notes.append(f"All {n} jobs are compatible and can be imposed on the same sheet.")
    else:
        notes.append(f"Jobs split into {len(groups)} compatible groups due to {len(hard_issues)} hard constraint(s).")

    return CompatibilityResult(
        compatible=all_compatible,
        groups=[[jobs[i].job_id for i in group] for group in groups],
        issues=issues,
        notes=notes,
    )

def find_compatible_groups(jobs: List[JobSpec], matrix: List[List[bool]]) -> List[List[int]]:
    """Group jobs that are all mutually compatible using union-find."""
    n = len(jobs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j]:
                union(i, j)

    groups = {}
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(i)

    return list(groups.values())

# ── IMPRESSION ALIGNMENT ──

def calculate_impressions(quantity: int, cartons_per_sheet: int) -> int:
    """Calculate impressions needed — always round up."""
    if cartons_per_sheet == 0:
        return 0
    return math.ceil(quantity / cartons_per_sheet)

def calculate_overrun(quantity: int, cartons_per_sheet: int, impressions: int) -> Tuple[int, float]:
    """Returns actual_printed and overrun_pct."""
    actual = cartons_per_sheet * impressions
    overrun_pct = round(((actual - quantity) / quantity) * 100, 2)
    return actual, overrun_pct

def calculate_alignment_score(impressions_dict: Dict[str, int]) -> float:
    """
    Score = 1 - (max - min) / max
    1.0 = all jobs finish at exactly same impression
    0.0 = completely misaligned
    """
    values = list(impressions_dict.values())
    if not values or max(values) == 0:
        return 0.0
    return round(1 - (max(values) - min(values)) / max(values), 4)

# ── MULTI-SKU LAYOUT ──

def calculate_multi_sku_layout(req: SheetPlanRequest) -> MultiSKULayoutResponse:
    """
    Main multi-SKU layout algorithm:
    1. Calculate flat sizes for all jobs
    2. Find best impression-aligned carton counts
    3. Assign sheet bands to each job
    4. Place cartons within each band
    """
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2

    jobs = req.jobs
    n = len(jobs)
    layout_notes = []

    # Step 1: Get flat sizes
    flat_sizes = {}
    for job in jobs:
        fw, fh, _, _ = get_flat_size_for_job(job)
        flat_sizes[job.job_id] = (fw, fh)

    # Step 2: Find best alignment
    analysis = analyse_impression_alignment(req)
    best = analysis.best_option
    layout_notes.append(analysis.recommendation)

    # Step 3: Assign bands and place cartons
    all_cartons = []
    jobs_summary = []
    current_y = req.margin

    # Sort jobs by flat height descending for band assignment
    sorted_jobs = sorted(jobs, key=lambda j: flat_sizes[j.job_id][1], reverse=True)

    for idx, job in enumerate(sorted_jobs):
        fw, fh = flat_sizes[job.job_id]
        cartons_per_sheet = best.cartons_per_job.get(job.job_id, 0)
        if cartons_per_sheet == 0:
            continue

        cols = int(usable_w // fw)
        if cols == 0:
            layout_notes.append(f"Warning: {job.product_name} flat width {fw}mm exceeds usable sheet width {usable_w}mm.")
            continue

        rows = math.ceil(cartons_per_sheet / cols)
        color = get_job_color(idx)
        impressions = best.impressions_per_job.get(job.job_id, 0)
        actual, overrun_pct = calculate_overrun(job.quantity, cartons_per_sheet, impressions)

        # Place cartons in band
        placed = 0
        for row in range(rows):
            for col in range(cols):
                if placed >= cartons_per_sheet:
                    break
                x = req.margin + col * fw
                y = current_y + row * fh
                all_cartons.append(MultiSKUCartonPosition(
                    job_id=job.job_id,
                    product_name=job.product_name,
                    x=x, y=y,
                    w=fw, h=fh,
                    flipped=False,
                    row=row, col=col,
                    color=color
                ))
                placed += 1

        current_y += rows * fh + 2  # 2mm gap between job bands

        jobs_summary.append(JobLayoutSummary(
            job_id=job.job_id,
            client_name=job.client_name,
            product_name=job.product_name,
            cartons_per_sheet=cartons_per_sheet,
            impressions_needed=impressions,
            actual_printed=actual,
            overrun_pct=overrun_pct,
            flat_w=fw,
            flat_h=fh,
            color=color,
        ))

        if overrun_pct > req.overrun_tolerance_pct:
            layout_notes.append(
                f"Warning: {job.product_name} has {overrun_pct}% overrun "
                f"(threshold: {req.overrun_tolerance_pct}%). "
                f"Consider adjusting quantity or sheet size."
            )

    # Calculate total utilization
    total_area = sum(
        c.w * c.h for c in all_cartons
    )
    utilization = round(total_area / (usable_w * usable_h) * 100, 2)

    overrun_warning = any(j.overrun_pct > req.overrun_tolerance_pct for j in jobs_summary)

    return MultiSKULayoutResponse(
        sheet_w=req.sheet_w,
        sheet_h=req.sheet_h,
        margin=req.margin,
        total_cartons_per_sheet=len(all_cartons),
        utilization=utilization,
        target_impressions=best.target_impressions,
        impression_alignment_score=best.alignment_score,
        overrun_warning=overrun_warning,
        jobs_summary=jobs_summary,
        cartons=all_cartons,
        layout_notes=layout_notes,
    )

# ── IMPRESSION ALIGNMENT ANALYSIS ──

def analyse_impression_alignment(req: SheetPlanRequest) -> AlignmentAnalysisResponse:
    """
    Find all viable carton count combinations and rank by alignment score.
    For each job, try different carton counts (1 to max_fit).
    Find the combination where impressions_needed are closest across all jobs.
    """
    usable_w = req.sheet_w - req.margin * 2
    usable_h = req.sheet_h - req.margin * 2
    jobs = req.jobs

    # Get flat sizes and max cartons per job
    flat_sizes = {}
    max_cartons = {}
    for job in jobs:
        fw, fh, _, _ = get_flat_size_for_job(job)
        flat_sizes[job.job_id] = (fw, fh)
        cols = int(usable_w // fw)
        rows = int(usable_h // fh)
        max_cartons[job.job_id] = cols * rows

    # Generate viable counts for each job (1 to max, in steps of cols)
    viable_counts = {}
    for job in jobs:
        fw, fh = flat_sizes[job.job_id]
        cols = max(1, int(usable_w // fw))
        counts = []
        c = cols
        while c <= max_cartons[job.job_id]:
            counts.append(c)
            c += cols
        if not counts:
            counts = [1]
        viable_counts[job.job_id] = counts

    # Try all combinations
    job_ids = [j.job_id for j in jobs]
    count_combinations = list(itertools.product(*[viable_counts[jid] for jid in job_ids]))

    options = []
    for combo in count_combinations:
        cartons_per_job = {job_ids[i]: combo[i] for i in range(len(job_ids))}

        # Check total fits on sheet
        total_rows_needed = sum(
            math.ceil(cartons_per_job[jid] / max(1, int(usable_w // flat_sizes[jid][0]))) *
            flat_sizes[jid][1]
            for jid in job_ids
        )
        if total_rows_needed > usable_h:
            continue

        # Calculate impressions
        impressions_per_job = {
            jid: calculate_impressions(
                next(j.quantity for j in jobs if j.job_id == jid),
                cartons_per_job[jid]
            )
            for jid in job_ids
        }

        alignment_score = calculate_alignment_score(impressions_per_job)
        target_impressions = max(impressions_per_job.values())

        # Calculate overrun
        max_overrun = 0
        for job in jobs:
            actual, overrun_pct = calculate_overrun(
                job.quantity,
                cartons_per_job[job.job_id],
                impressions_per_job[job.job_id]
            )
            max_overrun = max(max_overrun, overrun_pct)

        total_cartons = sum(cartons_per_job.values())
        total_area = sum(
            cartons_per_job[jid] * flat_sizes[jid][0] * flat_sizes[jid][1]
            for jid in job_ids
        )
        utilization = round(total_area / (usable_w * usable_h) * 100, 2)

        options.append(AlignmentOption(
            cartons_per_job=cartons_per_job,
            impressions_per_job=impressions_per_job,
            target_impressions=target_impressions,
            alignment_score=alignment_score,
            max_overrun_pct=max_overrun,
            total_cartons_per_sheet=total_cartons,
            utilization=utilization,
        ))

    if not options:
        # Fallback — max cartons for each job
        cartons_per_job = {jid: max_cartons[jid] for jid in job_ids}
        impressions_per_job = {
            jid: calculate_impressions(
                next(j.quantity for j in jobs if j.job_id == jid),
                cartons_per_job[jid]
            )
            for jid in job_ids
        }
        options.append(AlignmentOption(
            cartons_per_job=cartons_per_job,
            impressions_per_job=impressions_per_job,
            target_impressions=max(impressions_per_job.values()),
            alignment_score=calculate_alignment_score(impressions_per_job),
            max_overrun_pct=0,
            total_cartons_per_sheet=sum(cartons_per_job.values()),
            utilization=0,
        ))

    # Sort by alignment score descending, then by utilization descending
    options.sort(key=lambda o: (o.alignment_score, o.utilization), reverse=True)

    best = options[0]

    # Build recommendation message
    impressions_list = list(best.impressions_per_job.values())
    if best.alignment_score == 1.0:
        recommendation = (
            f"Perfect impression alignment at {best.target_impressions} impressions. "
            f"All jobs complete in the same press run — color consistency guaranteed."
        )
    elif best.alignment_score >= 0.9:
        recommendation = (
            f"Near-perfect alignment (score: {best.alignment_score}). "
            f"Max {best.target_impressions} impressions. "
            f"Minor overrun on some jobs but within acceptable range."
        )
    else:
        recommendation = (
            f"Best available alignment score: {best.alignment_score}. "
            f"Consider adjusting quantities or sheet size for better alignment."
        )

    return AlignmentAnalysisResponse(
        sheet_w=req.sheet_w,
        sheet_h=req.sheet_h,
        best_option=best,
        all_options=options[:10],  # Return top 10 options
        recommendation=recommendation,
    )
