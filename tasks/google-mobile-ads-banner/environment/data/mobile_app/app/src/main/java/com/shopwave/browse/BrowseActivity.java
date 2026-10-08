package com.shopwave.browse;

import com.shopwave.platform.Activity;
import com.shopwave.platform.LinearLayout;
import com.shopwave.platform.TextView;

import java.util.List;

public final class BrowseActivity extends Activity {
    private final List<Product> products;
    private final LinearLayout root = new LinearLayout();
    private final RecyclerView productFeed = new RecyclerView();
    private final TextView sponsoredStatus = new TextView("Loading sponsored content");
    private ProductFeedAdapter adapter;

    public BrowseActivity(List<Product> products) {
        this.products = List.copyOf(products);
    }

    public void onCreate() {
        adapter = new ProductFeedAdapter(products);
        productFeed.setAdapter(adapter);
        root.addView(productFeed);
        root.addView(sponsoredStatus);
        initializeBanner();
    }

    private void initializeBanner() {
        // TODO: Implement the sponsored banner described in docs/banner_integration_brief.md.
    }

    public LinearLayout getRoot() {
        return root;
    }

    public RecyclerView getProductFeed() {
        return productFeed;
    }

    public ProductFeedAdapter getAdapter() {
        return adapter;
    }

    public TextView getSponsoredStatus() {
        return sponsoredStatus;
    }

    public List<Product> search(String query) {
        return adapter.search(query);
    }

    public void refresh() {
        adapter.refresh();
    }
}
