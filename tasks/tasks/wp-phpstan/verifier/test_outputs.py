from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest


RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
PROJECT = RESULTS / "parcelpilot"
SOURCE = Path(os.environ.get("TASK_DATA_PROJECT", "/root/data/parcelpilot"))
CHECKER_PATH = Path(os.environ.get("WP_PHPSTAN_CHECKER", "/opt/task/wp_phpstan_check.py"))
PHP_BIN = os.environ.get("PHP_BIN", "php")


@pytest.fixture(scope="module")
def checker_module():
    assert CHECKER_PATH.is_file(), f"offline analyzer fixture is unavailable: {CHECKER_PATH}"
    spec = importlib.util.spec_from_file_location("wp_phpstan_check", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def category_errors(checker_module):
    if not PROJECT.is_dir():
        return {
            "config": ["output project is missing"],
            "wordpress": ["output project is missing"],
            "third-party": ["output project is missing"],
        }
    return {
        category: checker_module.all_errors(PROJECT, category)
        for category in ("config", "wordpress", "third-party")
    }


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path} must contain a JSON object"
    return payload


@pytest.mark.parametrize("case", ["analyzer_config", "baseline", "dependencies", "lockfile"])
def test_configuration_scope_and_change_boundaries(case, category_errors):
    assert PROJECT.is_dir(), "output project is missing"
    if case == "analyzer_config":
        assert category_errors["config"] == [], (
            "the PHPStan scope, baseline include, or WordPress core stub setup is still unsafe: "
            + " | ".join(category_errors["config"])
        )
    elif case == "baseline":
        assert (PROJECT / "phpstan-baseline.neon").read_bytes() == (
            SOURCE / "phpstan-baseline.neon"
        ).read_bytes(), "the legacy baseline changed even though the task froze it"
    elif case == "dependencies":
        original = _load_json(SOURCE / "composer.json")
        submitted = _load_json(PROJECT / "composer.json")
        for section in ("require", "require-dev"):
            assert submitted.get(section) == original.get(section), (
                f"Composer {section} changed even though dependency changes were not allowed"
            )
    else:
        assert (PROJECT / "composer.lock").read_bytes() == (SOURCE / "composer.lock").read_bytes(), (
            "composer.lock changed despite the frozen dependency set"
        )


@pytest.mark.parametrize(
    "file_fragment",
    [
        "src/Rest/OrdersController.php",
        "src/Hooks/OrderStatusHooks.php",
        "src/Repository/PickListRepository.php",
        "src/Jobs/CarrierSyncJob.php",
    ],
)
def test_wordpress_type_outcomes(file_fragment, category_errors):
    relevant = [error for error in category_errors["wordpress"] if file_fragment in error]
    assert not relevant, (
        f"WordPress dynamic values in {file_fragment} remain too imprecise for safe analysis: "
        + " | ".join(relevant)
    )


@pytest.mark.parametrize("case", ["woocommerce", "loyalty", "suppression_scope"])
def test_third_party_resolution_safety(case, category_errors):
    errors = category_errors["third-party"]
    if case == "woocommerce":
        relevant = [error for error in errors if "WC_Order" in error or "WooCommerceBridge" in error]
    elif case == "loyalty":
        relevant = [error for error in errors if "Vendor_Loyalty_Card" in error]
    else:
        relevant = [error for error in errors if "suppress unrelated" in error]
    assert not relevant, (
        f"third-party handling remains incomplete or can conceal unrelated defects ({case}): "
        + " | ".join(relevant)
    )
