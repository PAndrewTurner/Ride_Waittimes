"""Tests for parkwaits configuration."""

from parkwaits.config import (
    DATA_DIR,
    PARK_ENTITIES,
    PARK_SLUGS,
    QUEUETIMES_PARK_IDS,
    WDW_PARKS,
    UNI_PARKS,
)


def test_all_parks_have_required_keys():
    required = {"name", "resort", "entity_id", "lat", "lon", "is_water_park"}
    for slug, info in PARK_ENTITIES.items():
        missing = required - set(info.keys())
        assert not missing, f"Park {slug} missing keys: {missing}"


def test_park_slugs_match_entities():
    assert set(PARK_SLUGS) == set(PARK_ENTITIES.keys())


def test_wdw_parks():
    assert WDW_PARKS == {"mk", "epcot", "hs", "ak"}


def test_uni_parks():
    assert UNI_PARKS == {"usf", "ioa", "vb", "eu"}


def test_coordinates_in_range():
    for slug, info in PARK_ENTITIES.items():
        assert 28.0 <= info["lat"] <= 29.0, f"{slug} lat out of range: {info['lat']}"
        assert -82.0 <= info["lon"] <= -81.0, f"{slug} lon out of range: {info['lon']}"


def test_all_parks_in_queuetimes():
    for slug in PARK_ENTITIES:
        assert slug in QUEUETIMES_PARK_IDS, f"Park {slug} missing from QUEUETIMES_PARK_IDS"


def test_data_dir_name():
    assert DATA_DIR.name == "data"
