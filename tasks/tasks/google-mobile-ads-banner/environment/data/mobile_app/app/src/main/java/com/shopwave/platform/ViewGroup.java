package com.shopwave.platform;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class ViewGroup extends View {
    private final List<View> children = new ArrayList<>();

    public void addView(View child) {
        UiRuntime.assertMainThread();
        child.attachTo(this);
        if (!children.contains(child)) {
            children.add(child);
        }
    }

    public List<View> getChildren() {
        return Collections.unmodifiableList(children);
    }
}
