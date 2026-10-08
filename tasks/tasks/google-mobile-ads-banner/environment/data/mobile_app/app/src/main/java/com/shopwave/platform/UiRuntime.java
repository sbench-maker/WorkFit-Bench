package com.shopwave.platform;

import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;

/** A tiny deterministic UI dispatcher used by the offline fixture. */
public final class UiRuntime {
    private static final Queue<Runnable> PENDING = new ConcurrentLinkedQueue<>();
    private static volatile Thread mainThread;

    private UiRuntime() {}

    public static void installForCurrentThread() {
        mainThread = Thread.currentThread();
        PENDING.clear();
    }

    public static boolean isMainThread() {
        return Thread.currentThread() == mainThread;
    }

    public static void assertMainThread() {
        if (!isMainThread()) {
            throw new IllegalStateException("UI mutation attempted off the main thread");
        }
    }

    public static void post(Runnable action) {
        PENDING.add(action);
    }

    public static void drain() {
        assertMainThread();
        Runnable action;
        while ((action = PENDING.poll()) != null) {
            action.run();
        }
    }
}
