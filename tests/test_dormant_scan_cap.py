from src.config import Settings
from src.orchestrator import _dormant_scan_cap


def test_scan_cap_unlimited_when_result_limit_zero():
    settings = Settings(tiflux_dormant_scan_max=0)
    assert _dormant_scan_cap(settings, 0) == 0


def test_scan_cap_optional_safety_cap_for_full_scan():
    settings = Settings(tiflux_dormant_scan_max=500)
    assert _dormant_scan_cap(settings, 0) == 500


def test_scan_cap_legacy_limit_mode():
    settings = Settings(tiflux_dormant_scan_max=0)
    assert _dormant_scan_cap(settings, 100) == 400
