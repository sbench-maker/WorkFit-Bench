package com.shopwave.platform;

public class View {
    public enum Visibility { VISIBLE, GONE }

    private ViewGroup parent;
    private Visibility visibility = Visibility.VISIBLE;

    public ViewGroup getParent() {
        return parent;
    }

    void attachTo(ViewGroup newParent) {
        if (parent != null && parent != newParent) {
            throw new IllegalStateException("View already has a parent");
        }
        parent = newParent;
    }

    public Visibility getVisibility() {
        return visibility;
    }

    public void setVisibility(Visibility visibility) {
        UiRuntime.assertMainThread();
        this.visibility = visibility;
    }
}
