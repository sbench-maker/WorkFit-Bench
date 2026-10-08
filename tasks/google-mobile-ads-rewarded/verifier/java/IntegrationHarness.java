package verifier;

import com.asterlane.game.RewardWallet;
import com.asterlane.game.RewardedBoostController;
import com.asterlane.game.RewardedBoostView;
import com.google.android.libraries.ads.mobile.sdk.rewarded.RewardItem;
import com.google.android.libraries.ads.mobile.sdk.rewarded.RewardedAd;
import com.google.android.libraries.ads.mobile.sdk.rewarded.testing.RewardedAdTestDriver;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.List;

public final class IntegrationHarness {
    private static final class View implements RewardedBoostView {
        boolean buttonEnabled;
        boolean unsafeUiCall;
        int dispatchDepth;
        final List<Boolean> buttonStates = new ArrayList<>();

        @Override
        public void setWatchButtonEnabled(boolean enabled) {
            if (RewardedAdTestDriver.isInSdkCallback() && dispatchDepth == 0) {
                unsafeUiCall = true;
            }
            buttonEnabled = enabled;
            buttonStates.add(enabled);
        }

        @Override
        public void showMessage(String message) {
            if (RewardedAdTestDriver.isInSdkCallback() && dispatchDepth == 0) {
                unsafeUiCall = true;
            }
        }

        @Override
        public void runOnUiThread(Runnable action) {
            dispatchDepth += 1;
            try {
                action.run();
            } finally {
                dispatchDepth -= 1;
            }
        }
    }

    private static final class Wallet implements RewardWallet {
        final List<String> rewards = new ArrayList<>();

        @Override
        public void credit(String rewardType, int amount) {
            rewards.add(rewardType + ":" + amount);
        }
    }

    private record Fixture(RewardedBoostController controller, View view, Wallet wallet) {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("one scenario name is required");
        }
        switch (args[0]) {
            case "smoke" -> smoke();
            case "loading" -> loadingAndReadiness();
            case "opt_in" -> explicitOptIn();
            case "reward" -> rewardIntegrity();
            case "recovery" -> callbackSafetyAndRecovery();
            default -> throw new IllegalArgumentException("unknown scenario: " + args[0]);
        }
        System.out.println("PASS " + args[0]);
    }

    private static Fixture fixture() {
        RewardedAdTestDriver.reset();
        View view = new View();
        Wallet wallet = new Wallet();
        return new Fixture(new RewardedBoostController(view, wallet), view, wallet);
    }

    private static RewardedAd loadReady(Fixture f) {
        f.controller.load();
        RewardedAd ad = new RewardedAd();
        RewardedAdTestDriver.completeLoad(ad);
        return ad;
    }

    private static void smoke() throws Exception {
        Class<?> cls = RewardedBoostController.class;
        check(Modifier.isPublic(cls.getModifiers()),
                "controller must remain a public replacement class");
        Constructor<?> constructor = cls.getConstructor(RewardedBoostView.class, RewardWallet.class);
        Method load = cls.getMethod("load");
        Method click = cls.getMethod("onWatchAdClicked");
        check(constructor != null && load.getReturnType() == void.class && click.getReturnType() == void.class,
                "starter constructor and public method contract changed");
    }

    private static void loadingAndReadiness() {
        Fixture f = fixture();
        check(!f.view.buttonEnabled, "watch button must start disabled");
        f.controller.load();
        check(RewardedAdTestDriver.getLoadCount() == 1, "load() must request exactly one ad");
        check(RewardedAdTestDriver.getPendingRequest() != null, "load() did not submit an AdRequest");
        check("demo-rewarded-boost".equals(RewardedAdTestDriver.getPendingRequest().getAdUnitId()),
                "load() used the wrong placement ad unit ID");
        check(!f.view.buttonEnabled, "button became available before an ad loaded");

        RewardedAd ad = new RewardedAd();
        RewardedAdTestDriver.completeLoad(ad);
        check(ad.getShowCount() == 0, "loading an ad must not present it automatically");
        check(ad.getAdEventCallback() != null, "a loaded ad needs its full-screen event callback");
        check(f.view.buttonEnabled, "successful load must make the opt-in button available");

        Fixture failed = fixture();
        failed.controller.load();
        RewardedAdTestDriver.failLoad("offline inventory miss");
        check(!failed.view.buttonEnabled, "failed load left the opt-in button available");
        failed.controller.onWatchAdClicked();
        check(failed.wallet.rewards.isEmpty(), "failed inventory must not grant a reward");
    }

    private static void explicitOptIn() {
        Fixture f = fixture();
        RewardedAd ad = loadReady(f);
        check(ad.getShowCount() == 0, "ad presented before explicit opt-in");
        f.controller.onWatchAdClicked();
        check(ad.getShowCount() == 1, "explicit watch-button action did not present the ready ad once");
        check(!f.view.buttonEnabled, "watch button stayed enabled while the ad was being consumed");
        f.controller.onWatchAdClicked();
        check(ad.getShowCount() == 1, "the same ad was presented more than once");
    }

    private static void rewardIntegrity() {
        Fixture f = fixture();
        RewardedAd ad = loadReady(f);
        f.controller.onWatchAdClicked();
        check(f.wallet.rewards.isEmpty(), "showing an ad granted a reward before the earned callback");
        ad.emitReward(new RewardItem("energy", 7));
        check(f.wallet.rewards.equals(List.of("energy:7")),
                "wallet did not receive exactly the SDK-provided reward type and amount");
        ad.emitDismissed();
        check(f.wallet.rewards.equals(List.of("energy:7")), "dismissal granted an extra reward");

        Fixture failed = fixture();
        RewardedAd failedAd = loadReady(failed);
        failed.controller.onWatchAdClicked();
        failedAd.emitFailedToShow("surface lost");
        check(failed.wallet.rewards.isEmpty(), "presentation failure granted an unearned reward");
    }

    private static void callbackSafetyAndRecovery() {
        Fixture dismissed = fixture();
        RewardedAd first = loadReady(dismissed);
        check(!dismissed.view.unsafeUiCall, "load-success callback changed UI outside runOnUiThread");
        dismissed.controller.onWatchAdClicked();
        first.emitDismissed();
        check(RewardedAdTestDriver.getLoadCount() == 2, "dismissal did not start replacement loading");
        check(!dismissed.view.buttonEnabled, "button became available before replacement inventory loaded");
        dismissed.controller.onWatchAdClicked();
        check(first.getShowCount() == 1, "dismissed ad reference was reused");
        RewardedAd second = new RewardedAd();
        RewardedAdTestDriver.completeLoad(second);
        check(dismissed.view.buttonEnabled, "replacement success did not restore readiness");
        check(!dismissed.view.unsafeUiCall, "dismissal/reload callbacks changed UI outside runOnUiThread");

        Fixture showFailure = fixture();
        RewardedAd failing = loadReady(showFailure);
        showFailure.controller.onWatchAdClicked();
        failing.emitFailedToShow("activity unavailable");
        check(RewardedAdTestDriver.getLoadCount() == 2, "presentation failure did not request a replacement");
        check(!showFailure.view.buttonEnabled, "presentation failure left the button ready with no ad");
        RewardedAdTestDriver.failLoad("replacement unavailable");
        check(!showFailure.view.unsafeUiCall, "failure callbacks changed UI outside runOnUiThread");
        showFailure.controller.onWatchAdClicked();
        check(failing.getShowCount() == 1, "failed-to-show ad reference was reused");
    }

    private static void check(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
