from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest


DATA = Path("/root/data")
OUTPUT = Path("/root/results/venue_service_map.geojson")


def geodesic_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Vincenty inverse distance on the WGS84 ellipsoid."""
    semi_major = 6378137.0
    flattening = 1 / 298.257223563
    semi_minor = (1 - flattening) * semi_major
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    reduced1 = math.atan((1 - flattening) * math.tan(phi1))
    reduced2 = math.atan((1 - flattening) * math.tan(phi2))
    sin1, cos1 = math.sin(reduced1), math.cos(reduced1)
    sin2, cos2 = math.sin(reduced2), math.cos(reduced2)
    longitude_delta = math.radians(lon2 - lon1)
    lam = longitude_delta
    for _ in range(100):
        sin_lam, cos_lam = math.sin(lam), math.cos(lam)
        sin_sigma = math.sqrt((cos2 * sin_lam) ** 2 + (cos1 * sin2 - sin1 * cos2 * cos_lam) ** 2)
        if sin_sigma == 0:
            return 0.0
        cos_sigma = sin1 * sin2 + cos1 * cos2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos1 * cos2 * sin_lam / sin_sigma
        cos_sq_alpha = 1 - sin_alpha**2
        cos_two_sigma_m = 0.0 if cos_sq_alpha == 0 else cos_sigma - 2 * sin1 * sin2 / cos_sq_alpha
        correction = flattening / 16 * cos_sq_alpha * (4 + flattening * (4 - 3 * cos_sq_alpha))
        previous = lam
        lam = longitude_delta + (1 - correction) * flattening * sin_alpha * (
            sigma
            + correction
            * sin_sigma
            * (cos_two_sigma_m + correction * cos_sigma * (-1 + 2 * cos_two_sigma_m**2))
        )
        if abs(lam - previous) < 1e-12:
            break
    u_sq = cos_sq_alpha * (semi_major**2 - semi_minor**2) / semi_minor**2
    coefficient_a = 1 + u_sq / 16384 * (4096 + u_sq * (-768 + u_sq * (320 - 175 * u_sq)))
    coefficient_b = u_sq / 1024 * (256 + u_sq * (-128 + u_sq * (74 - 47 * u_sq)))
    delta_sigma = coefficient_b * sin_sigma * (
        cos_two_sigma_m
        + coefficient_b
        / 4
        * (
            cos_sigma * (-1 + 2 * cos_two_sigma_m**2)
            - coefficient_b
            / 6
            * cos_two_sigma_m
            * (-3 + 4 * sin_sigma**2)
            * (-3 + 4 * cos_two_sigma_m**2)
        )
    )
    return semi_minor * coefficient_a * (sigma - delta_sigma)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def first_value(mapping: dict, aliases: tuple[str, ...]):
    for key in aliases:
        if key in mapping:
            return mapping[key]
    return None


def coalesce(*values):
    return next((value for value in values if value is not None), None)


def normalize_feature(feature: object) -> dict | None:
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties")
    if not isinstance(props, dict):
        props = {}
    source = props.get("source") if isinstance(props.get("source"), dict) else {}
    zone_raw = first_value(props, ("service_zone", "zone"))
    zone = zone_raw if isinstance(zone_raw, dict) else {}
    hub_raw = first_value(props, ("nearest_hub", "pickup_hub", "hub"))
    hub = hub_raw if isinstance(hub_raw, dict) else {}
    geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
    venue_id = coalesce(first_value(props, ("venue_id", "id")), first_value(source, ("venue_id", "id")), feature.get("id"))
    return {
        "venue_id": venue_id,
        "geometry_type": geometry.get("type"),
        "coordinates": geometry.get("coordinates"),
        "venue_name": coalesce(first_value(props, ("venue_name", "name")), first_value(source, ("venue_name", "name"))),
        "category": coalesce(first_value(props, ("category", "venue_category")), first_value(source, ("category", "venue_category"))),
        "street_address": coalesce(first_value(props, ("street_address", "address")), first_value(source, ("street_address", "address"))),
        "status": coalesce(first_value(props, ("status", "venue_status")), first_value(source, ("status", "venue_status"))),
        "zone_id": coalesce(first_value(props, ("service_zone_id", "zone_id")), first_value(zone, ("zone_id", "id"))),
        "zone_name": coalesce(first_value(props, ("service_zone_name", "zone_name")), first_value(zone, ("zone_name", "name"))),
        "zone_value": zone_raw if not isinstance(zone_raw, dict) else None,
        "hub_id": coalesce(first_value(props, ("nearest_hub_id", "pickup_hub_id", "hub_id")), first_value(hub, ("hub_id", "id"))),
        "hub_name": coalesce(first_value(props, ("nearest_hub_name", "pickup_hub_name", "hub_name")), first_value(hub, ("hub_name", "name"))),
        "hub_value": hub_raw if not isinstance(hub_raw, dict) else None,
        "distance_m": coalesce(first_value(props, ("nearest_hub_distance_m", "hub_distance_m", "distance_m")), first_value(hub, ("distance_m", "distance"))),
    }


def normalized_output() -> tuple[dict | None, list[dict], dict[str, dict]]:
    doc = read_json(OUTPUT)
    if not isinstance(doc, dict) or not isinstance(doc.get("features"), list):
        return doc if isinstance(doc, dict) else None, [], {}
    features = [item for item in (normalize_feature(raw) for raw in doc["features"]) if item is not None]
    by_id = {}
    for feature in features:
        venue_id = feature.get("venue_id")
        if isinstance(venue_id, str) and venue_id not in by_id:
            by_id[venue_id] = feature
    return doc, features, by_id


def source_rows() -> list[dict[str, str]]:
    with (DATA / "venues.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def valid_coordinate(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        longitude = float(row["longitude"])
        latitude = float(row["latitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None
    return longitude, latitude


def expected_venues() -> dict[str, tuple[dict[str, str], tuple[float, float]]]:
    expected = {}
    for row in source_rows():
        coordinate = valid_coordinate(row)
        if row.get("status", "").strip().lower() == "active" and coordinate is not None:
            expected[row["venue_id"]] = (row, coordinate)
    return expected


def on_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> bool:
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    return abs(cross) <= 1e-11 and min(ax, bx) - 1e-11 <= px <= max(ax, bx) + 1e-11 and min(ay, by) - 1e-11 <= py <= max(ay, by) + 1e-11


def ring_covers(ring: list[list[float]], longitude: float, latitude: float) -> bool:
    inside = False
    for index in range(len(ring) - 1):
        ax, ay = ring[index]
        bx, by = ring[index + 1]
        if on_segment(longitude, latitude, ax, ay, bx, by):
            return True
        if (ay > latitude) != (by > latitude):
            crossing_x = (bx - ax) * (latitude - ay) / (by - ay) + ax
            if longitude < crossing_x:
                inside = not inside
    return inside


def zones() -> list[dict]:
    doc = json.loads((DATA / "service_zones.geojson").read_text(encoding="utf-8"))
    result = []
    for feature in doc["features"]:
        props = feature["properties"]
        result.append(
            {
                "zone_id": props["zone_id"],
                "zone_name": props["zone_name"],
                "priority": int(props["priority"]),
                "ring": feature["geometry"]["coordinates"][0],
            }
        )
    return result


def expected_zone(longitude: float, latitude: float) -> dict | None:
    candidates = [zone for zone in zones() if ring_covers(zone["ring"], longitude, latitude)]
    return min(candidates, key=lambda item: (item["priority"], item["zone_id"])) if candidates else None


def hubs() -> list[dict[str, str]]:
    with (DATA / "pickup_hubs.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def expected_hub(longitude: float, latitude: float) -> tuple[dict[str, str], float]:
    candidates = []
    for hub in hubs():
        distance = geodesic_distance_m(
            latitude, longitude, float(hub["latitude"]), float(hub["longitude"])
        )
        candidates.append((distance, hub["hub_id"], hub))
    distance, _, hub = min(candidates, key=lambda item: (item[0], item[1]))
    return hub, distance


def test_geojson_artifact_usability():
    doc, features, _ = normalized_output()
    assert OUTPUT.is_file(), "the requested venue_service_map.geojson file is missing"
    assert doc is not None, "the requested map layer is not readable JSON"
    assert doc.get("type") == "FeatureCollection", "the map layer must be a GeoJSON FeatureCollection"
    assert features, "the FeatureCollection must contain usable venue features"
    assert len(features) == len(doc["features"]), "every FeatureCollection item must be a JSON feature object"
    for feature in features:
        assert feature["geometry_type"] == "Point", "every mapped venue must use Point geometry"
        coordinates = feature["coordinates"]
        assert isinstance(coordinates, list) and len(coordinates) >= 2, "every point needs longitude and latitude"
        assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in coordinates[:2]), "point coordinates must be finite numbers"
        assert isinstance(feature["venue_id"], str) and feature["venue_id"], "every point must expose its source venue ID"


def test_feature_scope_and_coordinates():
    _, features, by_id = normalized_output()
    expected = expected_venues()
    assert len(features) == len(by_id), "duplicate or unidentified venue features make the layer ambiguous"
    assert set(by_id) == set(expected), "the layer must contain exactly the active venues with valid coordinates"
    for venue_id, (_, coordinate) in expected.items():
        actual = by_id[venue_id]["coordinates"]
        assert isinstance(actual, list) and len(actual) >= 2, f"{venue_id} has no usable point coordinates"
        assert float(actual[0]) == pytest.approx(coordinate[0], abs=1e-8), f"{venue_id} longitude is incorrect or coordinate order is reversed"
        assert float(actual[1]) == pytest.approx(coordinate[1], abs=1e-8), f"{venue_id} latitude is incorrect or coordinate order is reversed"


def test_source_metadata_preserved():
    _, _, by_id = normalized_output()
    expected = expected_venues()
    assert set(by_id) == set(expected), "metadata cannot be reconciled because venue scope is incomplete"
    for venue_id, (row, _) in expected.items():
        actual = by_id[venue_id]
        for field in ("venue_name", "category", "street_address", "status"):
            assert actual[field] == row[field], f"{venue_id} does not preserve source {field}"


def test_all_zone_assignments():
    _, _, by_id = normalized_output()
    expected = expected_venues()
    assert set(by_id) == set(expected), "zone assignments cannot be complete when venue scope is incomplete"
    for venue_id, (_, coordinate) in expected.items():
        zone = expected_zone(*coordinate)
        actual = by_id[venue_id]
        provided = [actual[key] for key in ("zone_id", "zone_name", "zone_value") if actual[key] is not None]
        if zone is None:
            assert not provided, f"{venue_id} is outside every service zone and must have a null zone"
        else:
            accepted = {zone["zone_id"], zone["zone_name"]}
            assert provided and all(value in accepted for value in provided), f"{venue_id} has the wrong covered service zone"


def test_zone_boundary_overlap_and_null_cases():
    _, _, by_id = normalized_output()
    cases = {
        "VEN-EDGE-01": "ZN-NORTH",
        "VEN-EDGE-02": "ZN-CENTRAL",
        "VEN-EDGE-03": "ZN-EAST",
        "VEN-EDGE-04": "ZN-NORTH",
        "VEN-OUT-01": None,
    }
    assert set(cases) <= set(by_id), "boundary and out-of-zone venues must remain in the map layer"
    for venue_id, zone_id in cases.items():
        actual = by_id[venue_id]
        provided = [actual[key] for key in ("zone_id", "zone_name", "zone_value") if actual[key] is not None]
        if zone_id is None:
            assert not provided, f"{venue_id} violates null-zone handling"
        else:
            zone = next(item for item in zones() if item["zone_id"] == zone_id)
            assert provided and all(value in {zone["zone_id"], zone["zone_name"]} for value in provided), f"{venue_id} violates boundary coverage or overlap priority"


@pytest.mark.parametrize("bucket", range(5))
def test_nearest_hub_and_spheroid_distance(bucket: int):
    _, _, by_id = normalized_output()
    expected = expected_venues()
    group = [venue_id for index, venue_id in enumerate(sorted(expected)) if index % 5 == bucket]
    assert group, "distance test fixture bucket unexpectedly has no venues"
    missing = [venue_id for venue_id in group if venue_id not in by_id]
    assert not missing, f"distance results are missing venues in bucket {bucket}: {missing[:4]}"
    for venue_id in group:
        _, coordinate = expected[venue_id]
        hub, distance = expected_hub(*coordinate)
        actual = by_id[venue_id]
        provided_hub = [actual[key] for key in ("hub_id", "hub_name", "hub_value") if actual[key] is not None]
        assert provided_hub and all(value in {hub["hub_id"], hub["hub_name"]} for value in provided_hub), f"{venue_id} is linked to the wrong nearest pickup hub"
        try:
            actual_distance = float(actual["distance_m"])
        except (TypeError, ValueError):
            pytest.fail(f"{venue_id} lacks a numeric nearest-hub distance in meters")
        tolerance = max(1.0, distance * 0.0002)
        assert actual_distance == pytest.approx(distance, abs=tolerance), f"{venue_id} distance is not a WGS84 spheroid distance in meters"
