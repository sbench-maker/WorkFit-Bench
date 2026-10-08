from __future__ import annotations

import csv
import os
import re
import subprocess
import tempfile
from pathlib import Path


PROJECT = Path(os.environ.get("SKILLSBENCH_RESULTS_ROOT", "/root/results")) / "mobile_app"
TEST_AD_UNIT = "ca-app-pub-3940256099942544/9214589741"

HARNESS = r'''
import com.google.android.libraries.ads.mobile.sdk.banner.AdSize;
import com.google.android.libraries.ads.mobile.sdk.banner.AdView;
import com.google.android.libraries.ads.mobile.sdk.banner.BannerAdRequest;
import com.google.android.libraries.ads.mobile.sdk.banner.MockAdServer;
import com.shopwave.browse.BrowseActivity;
import com.shopwave.browse.Product;
import com.shopwave.browse.ProductCatalog;
import com.shopwave.platform.UiRuntime;
import com.shopwave.platform.View;

import java.nio.file.Path;
import java.util.List;
import java.util.Locale;

public final class BannerVerifierHarness {
    private record Screen(BrowseActivity activity, AdView banner) {}

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static Screen create(MockAdServer.Outcome outcome, String catalog) throws Exception {
        UiRuntime.installForCurrentThread();
        MockAdServer.reset(outcome);
        List<Product> products = ProductCatalog.load(Path.of(catalog));
        BrowseActivity activity = new BrowseActivity(products);
        activity.onCreate();
        MockAdServer.awaitCallbacks();
        UiRuntime.drain();
        List<AdView> banners = activity.getAdapter().getEntries().stream()
                .filter(AdView.class::isInstance).map(AdView.class::cast).toList();
        require(banners.size() == 1, "expected exactly one sponsored banner in the feed, found " + banners.size());
        return new Screen(activity, banners.get(0));
    }

    private static boolean containsAny(String value, String... terms) {
        String normalized = value == null ? "" : value.toLowerCase(Locale.ROOT);
        for (String term : terms) if (normalized.contains(term)) return true;
        return false;
    }

    public static void main(String[] args) throws Exception {
        require(args.length == 2, "usage: scenario catalog.csv");
        String scenario = args[0];
        String catalog = args[1];
        if (scenario.equals("placement")) {
            Screen screen = create(MockAdServer.Outcome.SUCCESS, catalog);
            int index = screen.activity().getAdapter().getEntries().indexOf(screen.banner());
            require(index == 6, "sponsored banner must follow the first six products; observed index " + index);
            require(screen.banner().getParent() == screen.activity().getProductFeed(),
                    "banner is not attached to the scrolling product feed");
            BannerAdRequest request = screen.banner().getLastRequest();
            require(request != null, "banner did not retain a load request");
            require(request.getAdSize().getFormat() == AdSize.Format.INLINE_CURRENT_ORIENTATION,
                    "scrolling feed requires an inline adaptive banner");
            require(request.getAdSize().getWidth() == 360,
                    "development banner width must match the 360 dp fixture viewport");
        } else if (scenario.equals("request")) {
            Screen screen = create(MockAdServer.Outcome.SUCCESS, catalog);
            BannerAdRequest request = screen.banner().getLastRequest();
            require(request != null, "no banner request was loaded");
            require("ca-app-pub-3940256099942544/9214589741".equals(request.getAdUnitId()),
                    "development build must use the supplied Android test ad unit");
            require(request.getAdSize() != null, "request is missing its adaptive size");
            require(screen.banner().getLoadCount() == 1,
                    "Browse creation must issue one banner load, observed " + screen.banner().getLoadCount());
        } else if (scenario.equals("callbacks")) {
            Screen success = create(MockAdServer.Outcome.SUCCESS, catalog);
            String successText = success.activity().getSponsoredStatus().getText();
            require(success.banner().getVisibility() == View.Visibility.VISIBLE,
                    "successful banner remains hidden");
            require(containsAny(successText, "ready", "loaded", "available"),
                    "success status does not communicate readiness: " + successText);
            require(Thread.currentThread().getName().equals(success.activity().getSponsoredStatus().getLastUpdateThread()),
                    "success status was not updated on the UI thread");

            Screen failure = create(MockAdServer.Outcome.FAILURE, catalog);
            String failureText = failure.activity().getSponsoredStatus().getText();
            require(failure.banner().getVisibility() == View.Visibility.GONE,
                    "failed banner remains visible");
            require(containsAny(failureText, "unavailable", "failed", "error", "unable"),
                    "failure status does not communicate unavailability: " + failureText);
            require(Thread.currentThread().getName().equals(failure.activity().getSponsoredStatus().getLastUpdateThread()),
                    "failure status was not updated on the UI thread");
            require(!successText.equalsIgnoreCase(failureText), "success and failure states are indistinguishable");
        } else if (scenario.equals("browse")) {
            Screen screen = create(MockAdServer.Outcome.SUCCESS, catalog);
            require(screen.activity().getAdapter().getProductCount() == 240,
                    "banner integration changed the 240-product catalog count");
            long expectedTrail = ProductCatalog.load(Path.of(catalog)).stream()
                    .filter(product -> product.name().toLowerCase(Locale.ROOT).contains("trail")
                            || product.category().toLowerCase(Locale.ROOT).contains("trail"))
                    .count();
            require(screen.activity().search("TrAiL").size() == expectedTrail,
                    "case-insensitive catalog search regressed");
            screen.activity().refresh();
            screen.activity().refresh();
            require(screen.activity().getAdapter().getRefreshCount() == 2,
                    "refresh behavior no longer records both refresh actions");
            require(screen.activity().getAdapter().getProductCount() == 240,
                    "refresh changed the catalog membership");
        } else {
            throw new IllegalArgumentException("unknown scenario " + scenario);
        }
    }
}
'''


def _build() -> subprocess.CompletedProcess[str]:
    launcher = PROJECT / "gradlew"
    if not launcher.is_file():
        return subprocess.CompletedProcess([], 127, "", f"missing build launcher: {launcher}")
    return subprocess.run(
        ["bash", str(launcher), "build", "-x", "test"],
        cwd=PROJECT,
        text=True,
        capture_output=True,
        timeout=90,
    )


def _run_harness(scenario: str) -> subprocess.CompletedProcess[str]:
    build = _build()
    assert build.returncode == 0, (
        "the offline project build failed, so runtime banner behavior is unavailable:\n"
        + build.stdout
        + build.stderr
    )
    with tempfile.TemporaryDirectory(prefix="banner-verifier-") as raw_temp:
        temp = Path(raw_temp)
        source = temp / "BannerVerifierHarness.java"
        source.write_text(HARNESS, encoding="utf-8")
        compile_result = subprocess.run(
            [
                "javac", "--release", "17", "-encoding", "UTF-8",
                "-cp", str(PROJECT / "build/classes"),
                "-d", str(temp), str(source),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert compile_result.returncode == 0, "verifier harness could not link to the delivered project: " + compile_result.stderr
        return subprocess.run(
            [
                "java", "-cp", f"{temp}:{PROJECT / 'build/classes'}",
                "BannerVerifierHarness", scenario, str(PROJECT / "data/products.csv"),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )


def test_artifact_builds_and_is_complete() -> None:
    assert PROJECT.is_dir(), f"updated project is missing at {PROJECT}"
    required = [
        PROJECT / "gradlew",
        PROJECT / "data/products.csv",
        PROJECT / "app/src/main/java/com/shopwave/browse/BrowseActivity.java",
    ]
    missing = [str(path.relative_to(PROJECT)) for path in required if not path.is_file()]
    assert not missing, "delivered project is incomplete: " + ", ".join(missing)
    with (PROJECT / "data/products.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 240 and len({row["product_id"] for row in rows}) == 240, (
        "the frozen 240-product catalog was removed or altered"
    )
    result = _build()
    assert result.returncode == 0, "offline build failed:\n" + result.stdout + result.stderr
    assert (PROJECT / "build/shopwave-mobile.jar").is_file(), "build did not produce the project JAR"


def test_inline_banner_placement_and_size() -> None:
    result = _run_harness("placement")
    assert result.returncode == 0, result.stdout + result.stderr


def test_request_and_single_load() -> None:
    result = _run_harness("request")
    assert result.returncode == 0, result.stdout + result.stderr


def test_callback_ui_states_and_thread_safety() -> None:
    result = _run_harness("callbacks")
    assert result.returncode == 0, result.stdout + result.stderr


def test_existing_browse_behavior_preserved() -> None:
    result = _run_harness("browse")
    assert result.returncode == 0, result.stdout + result.stderr


def test_production_handoff_note() -> None:
    assert PROJECT.is_dir(), f"updated project is missing at {PROJECT}"
    documents = []
    for path in PROJECT.rglob("*.md"):
        if "build" not in path.parts and path.name != "banner_integration_brief.md":
            documents.append(path.read_text(encoding="utf-8", errors="replace"))
    normalized = re.sub(r"\s+", " ", "\n".join(documents).lower())
    assert "test" in normalized and "ad unit" in normalized, (
        "handoff documentation does not identify the development ad unit as test traffic"
    )
    assert "production" in normalized and any(
        action in normalized for action in ("replace", "swap", "configure", "use")
    ), "handoff documentation does not tell release owners to configure a production ad unit"
    assert any(marker in normalized for marker in ("before release", "prior to release", "for release")), (
        "handoff note does not make the release-time action clear"
    )
