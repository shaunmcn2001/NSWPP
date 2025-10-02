import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.arcgis as arcgis  # noqa: E402
from app.arcgis import normalize_lotplan
from app.config import (
    PARCEL_LOT_FIELD,
    PARCEL_LOTPLAN_FIELD,
    PARCEL_PLAN_FIELD,
    PARCEL_SECTION_FIELD,
)


def _fc_with_feature():
    return {"type": "FeatureCollection", "features": [{}]}


def test_normalize_lotplan_supports_section():
    assert normalize_lotplan("Lot 2 Section 5 DP 12345") == "2/5/DP12345"


def test_normalize_lotplan_without_section():
    assert normalize_lotplan("lot 3 dp 45678") == "3/DP45678"


def test_fetch_parcel_geojson_includes_section_in_where(monkeypatch):
    calls = []

    def fake_query(service_url, layer_id, params, paginate=False):  # noqa: D401 - test helper
        where = params.get("where", "")
        calls.append(where)
        if PARCEL_SECTION_FIELD and f"UPPER({PARCEL_SECTION_FIELD})='5'" in where:
            return _fc_with_feature()
        return {"type": "FeatureCollection", "features": []}

    monkeypatch.setattr(arcgis, "_arcgis_geojson_query", fake_query)
    fc = arcgis.fetch_parcel_geojson("Lot 2 Sec 5 DP 12345")
    assert fc["features"], "expected section-aware query to return features"
    assert any(
        PARCEL_SECTION_FIELD in call and "='5'" in call for call in calls
    ), "section field not included in where clauses"


def test_fetch_parcel_geojson_prefers_combined_when_no_section(monkeypatch):
    calls = []

    def fake_query(service_url, layer_id, params, paginate=False):
        where = params.get("where", "")
        calls.append(where)
        return _fc_with_feature()

    monkeypatch.setattr(arcgis, "_arcgis_geojson_query", fake_query)
    fc = arcgis.fetch_parcel_geojson("13SP181800")
    assert fc["features"], "expected combined field lookup to return"
    assert calls[0] == f"UPPER({PARCEL_LOTPLAN_FIELD})='13SP181800'"
    assert len(calls) == 1, "combined lookup should short-circuit when results found"


def test_fetch_parcel_geojson_split_fields_without_section(monkeypatch):
    calls = []

    def fake_query(service_url, layer_id, params, paginate=False):
        where = params.get("where", "")
        calls.append(where)
        if f"UPPER({PARCEL_LOT_FIELD})=" in where and f"UPPER({PARCEL_PLAN_FIELD})=" in where:
            return _fc_with_feature()
        return {"type": "FeatureCollection", "features": []}

    monkeypatch.setattr(arcgis, "_arcgis_geojson_query", fake_query)
    fc = arcgis.fetch_parcel_geojson("Lot 7 DP 9999")
    assert fc["features"], "expected split-field fallback to return"
    split_clause = next(
        call
        for call in calls
        if f"UPPER({PARCEL_LOT_FIELD})=" in call and f"UPPER({PARCEL_PLAN_FIELD})=" in call
    )
    assert f"UPPER({PARCEL_LOT_FIELD})='7'" in split_clause
    assert f"UPPER({PARCEL_PLAN_FIELD})='DP9999'" in split_clause
    assert PARCEL_SECTION_FIELD not in split_clause or "=''" in split_clause
