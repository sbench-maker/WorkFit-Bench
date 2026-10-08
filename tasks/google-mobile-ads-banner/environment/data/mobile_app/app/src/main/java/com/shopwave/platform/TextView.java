package com.shopwave.platform;

public final class TextView extends View {
    private String text;
    private String lastUpdateThread;

    public TextView(String initialText) {
        UiRuntime.assertMainThread();
        text = initialText;
        lastUpdateThread = Thread.currentThread().getName();
    }

    public void setText(String value) {
        UiRuntime.assertMainThread();
        text = value;
        lastUpdateThread = Thread.currentThread().getName();
    }

    public String getText() {
        return text;
    }

    public String getLastUpdateThread() {
        return lastUpdateThread;
    }
}
