package com.google.android.libraries.ads.mobile.sdk.banner;

import java.util.ArrayList;
import java.util.List;

public final class MockAdServer {
    public enum Outcome { SUCCESS, FAILURE }

    private static final List<Thread> workers = new ArrayList<>();
    private static final List<Throwable> callbackFailures = new ArrayList<>();
    private static Outcome outcome = Outcome.SUCCESS;

    private MockAdServer() {}

    public static synchronized void reset(Outcome nextOutcome) {
        workers.clear();
        callbackFailures.clear();
        outcome = nextOutcome;
    }

    static synchronized Outcome outcome() {
        return outcome;
    }

    static synchronized void register(Thread worker) {
        workers.add(worker);
    }

    static synchronized void recordCallbackFailure(Throwable failure) {
        callbackFailures.add(failure);
    }

    public static void awaitCallbacks() throws InterruptedException {
        List<Thread> snapshot;
        synchronized (MockAdServer.class) {
            snapshot = List.copyOf(workers);
        }
        for (Thread worker : snapshot) {
            worker.join(2000);
            if (worker.isAlive()) {
                throw new IllegalStateException("Ad callback did not finish");
            }
        }
        synchronized (MockAdServer.class) {
            if (!callbackFailures.isEmpty()) {
                throw new IllegalStateException("Ad callback crashed", callbackFailures.get(0));
            }
        }
    }
}
