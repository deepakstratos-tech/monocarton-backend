from fastapi.testclient import TestClient
from main import app
from features.cartons.service import calculate_flat_size
from features.cartons.models import CartonSpecRequest

client = TestClient(app)

# ── HELPER ──

def layout_request(style="bottom_side_lock", L=45, W=45, H=83, sheet_w=700, sheet_h=1000, margin=10, nesting_pct_override=None):
    payload = {
        "style": style,
        "length": L,
        "width": W,
        "height": H,
        "sheet_w": sheet_w,
        "sheet_h": sheet_h,
        "margin": margin,
    }
    if nesting_pct_override is not None:
        payload["nesting_pct_override"] = nesting_pct_override
    return payload

# ══════════════════════════════════════════════════
# 1. HEALTH CHECK
# ══════════════════════════════════════════════════

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Mono Backend is running"

# ══════════════════════════════════════════════════
# 2. BOX STYLES ENDPOINT
# ══════════════════════════════════════════════════

def test_get_box_styles():
    response = client.get("/carton/styles")
    assert response.status_code == 200
    data = response.json()
    assert "bottom_side_lock" in data
    assert "straight_tuck_end" in data
    assert "reverse_tuck_end" in data
    assert "lock_bottom" in data

# ══════════════════════════════════════════════════
# 3. FLAT SIZE CALCULATIONS
# ══════════════════════════════════════════════════

def test_flat_size_bottom_side_lock():
    """Musli Power Capsule: L45 x W45 x H83 — Bottom Side Lock"""
    response = client.post("/carton/flat-size", json={
        "style": "bottom_side_lock",
        "length": 45,
        "width": 45,
        "height": 83
    })
    assert response.status_code == 200
    data = response.json()
    assert data["flat_w"] == 190.0       # 2(45+45) + 10
    assert data["flat_h"] == 157.7       # 83 + 33.2 + 41.5
    assert data["top_tuck_depth"] == 33.2  # 83 * 0.4
    assert data["bottom_tuck_depth"] == 41.5  # 83 * 0.5
    assert data["glue_flap"] == 10.0
    assert data["nesting_saving_mm"] == 33.2
    assert data["nesting_saving_pct"] == 21.05

def test_flat_size_vaav_syrup():
    """VAAV Syrup: L57 x W57 x H157 — Lock Bottom"""
    response = client.post("/carton/flat-size", json={
        "style": "lock_bottom",
        "length": 57,
        "width": 57,
        "height": 157
    })
    assert response.status_code == 200
    data = response.json()
    assert data["flat_w"] == 238.0       # 2(57+57) + 10
    assert data["top_tuck_depth"] == 62.8  # 157 * 0.4
    assert data["bottom_tuck_depth"] == 94.2  # 157 * 0.6

def test_flat_size_trujoint_plus():
    """Trujoint Plus: L110 x W88 x H140 — Bottom Side Lock"""
    response = client.post("/carton/flat-size", json={
        "style": "bottom_side_lock",
        "length": 110,
        "width": 88,
        "height": 140
    })
    assert response.status_code == 200
    data = response.json()
    assert data["flat_w"] == 406.0       # 2(110+88) + 10
    assert data["top_tuck_depth"] == 56.0  # 140 * 0.4

def test_flat_size_straight_tuck_end():
    """Straight Tuck End — both tucks same ratio"""
    response = client.post("/carton/flat-size", json={
        "style": "straight_tuck_end",
        "length": 45,
        "width": 45,
        "height": 83
    })
    assert response.status_code == 200
    data = response.json()
    assert data["flat_w"] == 190.0
    assert data["top_tuck_depth"] == 29.05   # 83 * 0.35
    assert data["bottom_tuck_depth"] == 29.05  # 83 * 0.35

def test_flat_size_invalid_style():
    """Invalid box style should return error"""
    response = client.post("/carton/flat-size", json={
        "style": "invalid_style",
        "length": 45,
        "width": 45,
        "height": 83
    })
    assert response.status_code == 400
    assert "Unknown box style" in response.json()["detail"]

def test_flat_size_custom_overrides():
    """Custom tuck flap and glue flap overrides"""
    response = client.post("/carton/flat-size", json={
        "style": "bottom_side_lock",
        "length": 45,
        "width": 45,
        "height": 83,
        "custom_top_tuck": 20.0,
        "custom_bottom_tuck": 30.0,
        "custom_glue_flap": 12.0
    })
    assert response.status_code == 200
    data = response.json()
    assert data["flat_w"] == 192.0       # 2(45+45) + 12
    assert data["top_tuck_depth"] == 20.0
    assert data["bottom_tuck_depth"] == 30.0
    assert data["glue_flap"] == 12.0

# ══════════════════════════════════════════════════
# 4. STRAIGHT LAYOUT
# ══════════════════════════════════════════════════

def test_straight_layout_musli_power():
    """Musli Power on 700x1000 sheet — straight layout"""
    response = client.post("/layout/straight", json=layout_request())
    assert response.status_code == 200
    data = response.json()
    assert data["layout_type"] == "straight"
    assert data["cartons_per_row"] == 3    # 680 / 190 = 3
    assert data["num_rows"] == 6           # 980 / 157.7 = 6
    assert data["total_cartons"] == 18
    assert data["flat_w"] == 190.0
    assert data["flat_h"] == 157.7

def test_straight_layout_carton_count():
    """Total cartons = cartons_per_row × num_rows"""
    response = client.post("/layout/straight", json=layout_request())
    data = response.json()
    assert data["total_cartons"] == data["cartons_per_row"] * data["num_rows"]

def test_straight_layout_carton_positions():
    """All carton positions should be within usable area"""
    response = client.post("/layout/straight", json=layout_request())
    data = response.json()
    margin = 10
    sheet_w = 700
    sheet_h = 1000
    for carton in data["cartons"]:
        assert carton["x"] >= margin
        assert carton["y"] >= margin
        assert carton["x"] + carton["w"] <= sheet_w - margin
        assert carton["y"] + carton["h"] <= sheet_h - margin

def test_straight_layout_no_flipped():
    """Straight layout should have no flipped cartons"""
    response = client.post("/layout/straight", json=layout_request())
    data = response.json()
    for carton in data["cartons"]:
        assert carton["flipped"] == False

def test_straight_layout_zero_cartons():
    """Carton larger than sheet should return 0 cartons"""
    response = client.post("/layout/straight", json=layout_request(
        L=400, W=400, H=500,
        sheet_w=300, sheet_h=300
    ))
    assert response.status_code == 200
    data = response.json()
    assert data["total_cartons"] == 0

def test_straight_layout_utilization_range():
    """Utilization should be between 0 and 100"""
    response = client.post("/layout/straight", json=layout_request())
    data = response.json()
    assert 0 <= data["utilization"] <= 100

# ══════════════════════════════════════════════════
# 5. TUMBLE LAYOUT
# ══════════════════════════════════════════════════

def layout_request_tumble_wins():
    """Sheet size where tumble gives more cartons than straight"""
    return layout_request(sheet_w=700, sheet_h=650)

def test_tumble_layout_musli_power():
    """Musli Power tumble layout should give more cartons than straight on 700x650 sheet"""
    straight = client.post("/layout/straight", json=layout_request_tumble_wins()).json()
    tumble = client.post("/layout/tumble", json=layout_request_tumble_wins()).json()
    assert tumble["total_cartons"] > straight["total_cartons"]
    assert straight["total_cartons"] == 9   # 3x3
    assert tumble["total_cartons"] == 12    # 3x4

def test_tumble_layout_has_flipped_cartons():
    """Tumble layout should have both normal and flipped cartons"""
    response = client.post("/layout/tumble", json=layout_request())
    data = response.json()
    flipped = [c for c in data["cartons"] if c["flipped"]]
    normal = [c for c in data["cartons"] if not c["flipped"]]
    assert len(flipped) > 0
    assert len(normal) > 0

def test_tumble_layout_nesting_saving():
    """Tumble layout should have positive nesting saving"""
    response = client.post("/layout/tumble", json=layout_request())
    data = response.json()
    assert data["nesting_saving_mm"] > 0
    assert data["nesting_saving_pct"] > 0
    assert data["pair_height"] > 0

def test_tumble_layout_pair_height():
    """Pair height should be less than 2 × flat height"""
    response = client.post("/layout/tumble", json=layout_request())
    data = response.json()
    assert data["pair_height"] < data["flat_h"] * 2

def test_tumble_layout_nesting_override():
    """Nesting override should affect total cartons"""
    default = client.post("/layout/tumble", json=layout_request()).json()
    override_high = client.post("/layout/tumble", json=layout_request(nesting_pct_override=40)).json()
    assert override_high["total_cartons"] >= default["total_cartons"]

def test_tumble_zero_nesting():
    """Tumble with 0% nesting should equal straight layout"""
    straight = client.post("/layout/straight", json=layout_request()).json()
    tumble_zero = client.post("/layout/tumble", json=layout_request(nesting_pct_override=0)).json()
    assert tumble_zero["total_cartons"] == straight["total_cartons"]

# ══════════════════════════════════════════════════
# 6. ALL LAYOUT ALGORITHMS
# ══════════════════════════════════════════════════

def test_first_fit_layout():
    response = client.post("/layout/first-fit", json=layout_request())
    assert response.status_code == 200
    data = response.json()
    assert data["layout_type"] == "first_fit"
    assert data["total_cartons"] > 0

def test_first_fit_decreasing_layout():
    response = client.post("/layout/first-fit-decreasing", json=layout_request())
    assert response.status_code == 200
    data = response.json()
    assert data["layout_type"] == "first_fit_decreasing"
    assert data["total_cartons"] > 0

def test_nfdh_layout():
    response = client.post("/layout/nfdh", json=layout_request())
    assert response.status_code == 200
    data = response.json()
    assert data["layout_type"] == "nfdh"
    assert data["total_cartons"] > 0

def test_best_fit_layout():
    response = client.post("/layout/best-fit", json=layout_request())
    assert response.status_code == 200
    data = response.json()
    assert data["layout_type"] == "best_fit"
    assert data["total_cartons"] > 0

# ══════════════════════════════════════════════════
# 7. COMPARE ENDPOINT
# ══════════════════════════════════════════════════

def test_compare_returns_all_algorithms():
    response = client.post("/layout/compare", json=layout_request())
    assert response.status_code == 200
    data = response.json()
    algorithms = [r["algorithm"] for r in data["comparison"]]
    assert "straight" in algorithms
    assert "tumble" in algorithms
    assert "first_fit" in algorithms
    assert "first_fit_decreasing" in algorithms
    assert "nfdh" in algorithms
    assert "best_fit" in algorithms

def test_compare_sorted_by_cartons():
    """Compare results should be sorted by total cartons descending"""
    response = client.post("/layout/compare", json=layout_request())
    data = response.json()
    counts = [r["total_cartons"] for r in data["comparison"]]
    assert counts == sorted(counts, reverse=True)

def test_compare_best_algorithm_is_correct():
    """Best algorithm should match the first item in comparison"""
    response = client.post("/layout/compare", json=layout_request())
    data = response.json()
    assert data["best_algorithm"] == data["comparison"][0]["algorithm"]
    assert data["best_total"] == data["comparison"][0]["total_cartons"]

def test_compare_tumble_beats_straight_for_musli():
    """For Musli Power on 700x650 sheet, tumble should beat straight"""
    response = client.post("/layout/compare", json=layout_request_tumble_wins())
    data = response.json()
    results = {r["algorithm"]: r["total_cartons"] for r in data["comparison"]}
    assert results["tumble"] > results["straight"]

# ══════════════════════════════════════════════════
# 8. REAL WORLD VALIDATION — MAYANK'S JOBS
# ══════════════════════════════════════════════════

def test_musli_power_flat_size():
    """Musli Power Capsule — validate flat size"""
    response = client.post("/carton/flat-size", json={
        "style": "bottom_side_lock",
        "length": 45, "width": 45, "height": 83
    })
    data = response.json()
    assert data["flat_w"] == 190.0
    assert data["flat_h"] == 157.7

def test_trujoint_plus_flat_size():
    """Trujoint Plus — validate flat size"""
    response = client.post("/carton/flat-size", json={
        "style": "bottom_side_lock",
        "length": 110, "width": 88, "height": 140
    })
    data = response.json()
    assert data["flat_w"] == 406.0

def test_vaav_syrup_flat_size():
    """VAAV Syrup — validate flat size"""
    response = client.post("/carton/flat-size", json={
        "style": "lock_bottom",
        "length": 57, "width": 57, "height": 157
    })
    data = response.json()
    assert data["flat_w"] == 238.0

def test_meplex_tablet_flat_size():
    """Meplex Tablet — validate flat size"""
    response = client.post("/carton/flat-size", json={
        "style": "bottom_side_lock",
        "length": 150, "width": 55, "height": 142
    })
    data = response.json()
    assert data["flat_w"] == 420.0   # 2(150+55) + 10