package com.shopwave.platform;

public class Activity {
    public void runOnUiThread(Runnable action) {
        if (UiRuntime.isMainThread()) {
            action.run();
        } else {
            UiRuntime.post(action);
        }
    }
}
