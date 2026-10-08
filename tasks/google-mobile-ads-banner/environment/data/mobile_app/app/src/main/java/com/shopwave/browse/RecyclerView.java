package com.shopwave.browse;

import com.shopwave.platform.ViewGroup;

public final class RecyclerView extends ViewGroup {
    private ProductFeedAdapter adapter;

    public void setAdapter(ProductFeedAdapter adapter) {
        this.adapter = adapter;
        adapter.attach(this);
    }

    public ProductFeedAdapter getAdapter() {
        return adapter;
    }
}
