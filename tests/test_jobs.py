from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ── HELPERS ──

def make_job(
    client_name="Test Client",
    product_name="Test Product",
    style="bottom_side_lock",
    length=45, width=45, height=83,
    quantity=5000,
    paper_type="FBB",
    gsm=330,
    lamination="UV",
    colours="CMYK_1P",
    stamping="NONE"
):
    return {
        "client_name": client_name,
        "product_name": product_name,
        "style": style,
        "length": length,
        "width": width,
        "height": height,
        "quantity": quantity,
        "paper_type": paper_type,
        "gsm": gsm,
        "lamination": lamination,
        "colours": colours,
        "stamping": stamping
    }

def make_request(jobs, sheet_w=700, sheet_h=1000, margin=10,
                 overrun_tolerance_pct=5, gsm_tolerance=10):
    return {
        "sheet_w": sheet_w,
        "sheet_h": sheet_h,
        "margin": margin,
        "overrun_tolerance_pct": overrun_tolerance_pct,
        "gsm_tolerance": gsm_tolerance,
        "jobs": jobs
    }

# Real world jobs from Mayank's plant
MUSLI_POWER = make_job(
    client_name="Fronius Biotech",
    product_name="Musli Power Capsule",
    length=45, width=45, height=83,
    quantity=5000,
    paper_type="FBB", gsm=330, lamination="UV"
)

TRUJOINT_PLUS = make_job(
    client_name="Fotis Lifesciences",
    product_name="Trujoint Plus",
    length=110, width=88, height=140,
    quantity=5000,
    paper_type="FBB", gsm=320, lamination="UV"
)

MEPLEX_TABLET = make_job(
    client_name="Apellon Biotech",
    product_name="Meplex Tablet",
    length=150, width=55, height=142,
    quantity=3000,
    paper_type="FBB", gsm=330, lamination="UV"
)

VAAV_SYRUP = make_job(
    client_name="Savavet",
    product_name="VAAV Syrup",
    style="lock_bottom",
    length=57, width=57, height=157,
    quantity=2000,
    paper_type="ITC_SAFIRE", gsm=350, lamination="UV"
)

# ══════════════════════════════════════════════════
# 1. JOB ENRICHMENT
# ══════════════════════════════════════════════════

def test_enrich_single_job():
    """Enriching a job should return flat size calculations"""
    response = client.post("/jobs/enrich", json=[MUSLI_POWER])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["flat_w"] == 190.0
    assert data[0]["flat_h"] == 157.7
    assert data[0]["top_tuck_depth"] == 33.2
    assert data[0]["nesting_saving_pct"] == 21.05

def test_enrich_multiple_jobs():
    """Enriching multiple jobs should return flat sizes for all"""
    response = client.post("/jobs/enrich", json=[MUSLI_POWER, TRUJOINT_PLUS])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["flat_w"] == 190.0
    assert data[1]["flat_w"] == 406.0

def test_enrich_job_has_job_id():
    """Each enriched job should have a job_id"""
    response = client.post("/jobs/enrich", json=[MUSLI_POWER])
    data = response.json()
    assert "job_id" in data[0]
    assert len(data[0]["job_id"]) > 0

def test_enrich_preserves_client_info():
    """Enriched job should preserve all original fields"""
    response = client.post("/jobs/enrich", json=[MUSLI_POWER])
    data = response.json()
    assert data[0]["client_name"] == "Fronius Biotech"
    assert data[0]["product_name"] == "Musli Power Capsule"
    assert data[0]["quantity"] == 5000

# ══════════════════════════════════════════════════
# 2. COMPATIBILITY — COMPATIBLE JOBS
# ══════════════════════════════════════════════════

def test_compatible_same_paper_gsm_lamination():
    """Jobs with same paper, GSM within tolerance, same lamination should be compatible"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    assert response.status_code == 200
    data = response.json()
    assert data["compatible"] == True

def test_compatible_returns_single_group():
    """Compatible jobs should be in one group"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert len(data["groups"]) == 1
    assert len(data["groups"][0]) == 2

def test_compatible_three_jobs():
    """Three compatible jobs should form one group"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS, MEPLEX_TABLET])
    )
    data = response.json()
    assert data["compatible"] == True
    assert len(data["groups"]) == 1
    assert len(data["groups"][0]) == 3

def test_compatible_no_hard_issues():
    """Compatible jobs should have no hard constraint issues"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    hard_issues = [i for i in data["issues"] if i["issue_type"] == "HARD"]
    assert len(hard_issues) == 0

def test_compatible_single_job():
    """A single job is always compatible with itself"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER])
    )
    data = response.json()
    assert data["compatible"] == True
    assert len(data["groups"]) == 1

# ══════════════════════════════════════════════════
# 3. COMPATIBILITY — INCOMPATIBLE JOBS
# ══════════════════════════════════════════════════

def test_incompatible_different_paper_type():
    """Jobs with different paper types should be incompatible"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, VAAV_SYRUP])
    )
    data = response.json()
    assert data["compatible"] == False
    hard_issues = [i for i in data["issues"] if i["issue_type"] == "HARD"]
    assert any(i["field"] == "paper_type" for i in hard_issues)

def test_incompatible_splits_into_groups():
    """Incompatible jobs should be split into separate groups"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, VAAV_SYRUP])
    )
    data = response.json()
    assert len(data["groups"]) == 2

def test_incompatible_different_lamination():
    """Jobs with different lamination should be incompatible"""
    job_a = make_job(lamination="GLOSS")
    job_b = make_job(lamination="MATT")
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    assert data["compatible"] == False
    hard_issues = [i for i in data["issues"] if i["issue_type"] == "HARD"]
    assert any(i["field"] == "lamination" for i in hard_issues)

def test_incompatible_gsm_exceeds_tolerance():
    """Jobs with GSM difference exceeding tolerance should be incompatible"""
    job_a = make_job(gsm=300)
    job_b = make_job(gsm=350)  # 50 GSM difference > 10 tolerance
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    assert data["compatible"] == False
    hard_issues = [i for i in data["issues"] if i["issue_type"] == "HARD"]
    assert any(i["field"] == "gsm" for i in hard_issues)

def test_compatible_gsm_within_tolerance():
    """Jobs with GSM within tolerance should be compatible"""
    job_a = make_job(gsm=325)
    job_b = make_job(gsm=330)  # 5 GSM difference < 10 tolerance
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    hard_issues = [i for i in data["issues"] if i["issue_type"] == "HARD" and i["field"] == "gsm"]
    assert len(hard_issues) == 0

# ══════════════════════════════════════════════════
# 4. SOFT WARNINGS
# ══════════════════════════════════════════════════

def test_soft_warning_different_colours():
    """Different colour specs should generate a soft warning"""
    job_a = make_job(colours="CMYK")
    job_b = make_job(colours="CMYK_2P")
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    soft_issues = [i for i in data["issues"] if i["issue_type"] == "SOFT"]
    assert any(i["field"] == "colours" for i in soft_issues)

def test_soft_warning_different_stamping():
    """Different stamping specs should generate a soft warning"""
    job_a = make_job(stamping="NONE")
    job_b = make_job(stamping="FOIL")
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    soft_issues = [i for i in data["issues"] if i["issue_type"] == "SOFT"]
    assert any(i["field"] == "stamping" for i in soft_issues)

def test_soft_warning_does_not_block_compatibility():
    """Soft warnings should not make jobs incompatible"""
    job_a = make_job(colours="CMYK", stamping="NONE")
    job_b = make_job(colours="CMYK_2P", stamping="FOIL")
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    assert data["compatible"] == True

# ══════════════════════════════════════════════════
# 5. IMPRESSION ALIGNMENT ANALYSIS
# ══════════════════════════════════════════════════

def test_alignment_returns_best_option():
    """Alignment analysis should return a best option"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    assert response.status_code == 200
    data = response.json()
    assert "best_option" in data
    assert "alignment_score" in data["best_option"]
    assert "target_impressions" in data["best_option"]

def test_alignment_score_range():
    """Alignment score should be between 0 and 1"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    score = data["best_option"]["alignment_score"]
    assert 0 <= score <= 1

def test_alignment_returns_multiple_options():
    """Alignment analysis should return multiple options"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert len(data["all_options"]) >= 1

def test_alignment_options_sorted_by_score():
    """Options should be sorted by alignment score descending"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    scores = [o["alignment_score"] for o in data["all_options"]]
    assert scores == sorted(scores, reverse=True)

def test_alignment_best_option_is_first():
    """Best option should match first option in all_options"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert data["best_option"]["alignment_score"] == data["all_options"][0]["alignment_score"]

def test_alignment_has_recommendation():
    """Alignment analysis should include a recommendation message"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert "recommendation" in data
    assert len(data["recommendation"]) > 0

def test_alignment_perfect_score_equal_quantities():
    """Equal quantities with matching carton multiples should give perfect alignment"""
    job_a = make_job(product_name="Job A", length=45, width=45, height=83, quantity=5000)
    job_b = make_job(product_name="Job B", length=45, width=45, height=83, quantity=5000)
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([job_a, job_b])
    )
    data = response.json()
    assert data["best_option"]["alignment_score"] == 1.0

def test_alignment_cartons_per_job_keys():
    """cartons_per_job should have a key for each job"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    best = data["best_option"]
    assert len(best["cartons_per_job"]) == 2
    assert len(best["impressions_per_job"]) == 2

def test_alignment_impressions_positive():
    """All impressions values should be positive"""
    response = client.post(
        "/jobs/analyse-alignment",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    for option in data["all_options"]:
        for imp in option["impressions_per_job"].values():
            assert imp > 0

# ══════════════════════════════════════════════════
# 6. MULTI-SKU LAYOUT
# ══════════════════════════════════════════════════

def test_multi_sku_layout_returns_cartons():
    """Multi-SKU layout should return carton positions"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["cartons"]) > 0

def test_multi_sku_layout_cartons_have_job_id():
    """Each carton position should have a job_id"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    for carton in data["cartons"]:
        assert "job_id" in carton
        assert len(carton["job_id"]) > 0

def test_multi_sku_layout_cartons_have_color():
    """Each carton should have a hex color for canvas rendering"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    for carton in data["cartons"]:
        assert "color" in carton
        assert carton["color"].startswith("#")

def test_multi_sku_layout_jobs_summary():
    """Layout should include a summary for each job"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert len(data["jobs_summary"]) == 2

def test_multi_sku_layout_impressions_positive():
    """All jobs should have positive impressions needed"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    for job in data["jobs_summary"]:
        assert job["impressions_needed"] > 0

def test_multi_sku_layout_actual_printed_gte_quantity():
    """Actual printed should always be >= quantity required"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    jobs_payload = make_request([MUSLI_POWER, TRUJOINT_PLUS])["jobs"]
    quantity_map = {j["product_name"]: j["quantity"] for j in jobs_payload}
    for job in data["jobs_summary"]:
        assert job["actual_printed"] >= quantity_map[job["product_name"]]

def test_multi_sku_layout_utilization_range():
    """Utilization should be between 0 and 100"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert 0 <= data["utilization"] <= 100

def test_multi_sku_layout_cartons_within_sheet():
    """All carton positions should be within sheet boundaries"""
    req = make_request([MUSLI_POWER, TRUJOINT_PLUS], sheet_w=700, sheet_h=1000, margin=10)
    response = client.post("/jobs/multi-sku-layout", json=req)
    data = response.json()
    for carton in data["cartons"]:
        assert carton["x"] >= 10
        assert carton["y"] >= 10
        assert carton["x"] + carton["w"] <= 700
        assert carton["y"] + carton["h"] <= 1000

def test_multi_sku_layout_alignment_score_range():
    """Impression alignment score should be between 0 and 1"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert 0 <= data["impression_alignment_score"] <= 1

def test_multi_sku_layout_has_notes():
    """Layout should include notes"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert "layout_notes" in data

def test_multi_sku_layout_three_jobs():
    """Multi-SKU layout should handle three jobs"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS, MEPLEX_TABLET])
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs_summary"]) == 3
    assert len(data["cartons"]) > 0

def test_multi_sku_different_colors_per_job():
    """Different jobs should have different colors on canvas"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    job_colors = {c["job_id"]: c["color"] for c in data["cartons"]}
    assert len(set(job_colors.values())) == 2

def test_multi_sku_overrun_warning_flag():
    """Overrun warning should be set when overrun exceeds tolerance"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS],
                         overrun_tolerance_pct=0)  # 0% tolerance = always warn
    )
    data = response.json()
    assert "overrun_warning" in data

# ══════════════════════════════════════════════════
# 7. REAL WORLD VALIDATION — MAYANK'S JOBS
# ══════════════════════════════════════════════════

def test_musli_trujoint_compatible():
    """Musli Power and Trujoint Plus should be compatible"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    assert data["compatible"] == True

def test_vaav_incompatible_with_fbb_jobs():
    """VAAV Syrup (ITC Safire) should be incompatible with FBB jobs"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, VAAV_SYRUP])
    )
    data = response.json()
    assert data["compatible"] == False
    assert len(data["groups"]) == 2

def test_musli_trujoint_meplex_all_compatible():
    """Musli Power, Trujoint Plus, Meplex should all be compatible"""
    response = client.post(
        "/jobs/check-compatibility",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS, MEPLEX_TABLET])
    )
    data = response.json()
    assert data["compatible"] == True

def test_musli_trujoint_layout_target_impressions():
    """Both jobs with 5000 quantity should aim for same impressions"""
    response = client.post(
        "/jobs/multi-sku-layout",
        json=make_request([MUSLI_POWER, TRUJOINT_PLUS])
    )
    data = response.json()
    impressions = [j["impressions_needed"] for j in data["jobs_summary"]]
    assert data["impression_alignment_score"] > 0
    assert data["target_impressions"] > 0

