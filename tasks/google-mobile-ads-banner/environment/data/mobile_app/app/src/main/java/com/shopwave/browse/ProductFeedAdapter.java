package com.shopwave.browse;

import com.google.android.libraries.ads.mobile.sdk.banner.AdView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

public final class ProductFeedAdapter {
    private final List<Object> entries;
    private RecyclerView host;
    private int refreshCount;

    public ProductFeedAdapter(List<Product> products) {
        entries = new ArrayList<>(products);
    }

    void attach(RecyclerView recyclerView) {
        host = recyclerView;
    }

    public void insertSponsoredView(int position, AdView adView) {
        if (host == null) {
            throw new IllegalStateException("Adapter must be attached before inserting a sponsored view");
        }
        if (position < 0 || position > entries.size()) {
            throw new IllegalArgumentException("Sponsored position is outside the feed");
        }
        if (entries.stream().anyMatch(AdView.class::isInstance)) {
            throw new IllegalStateException("The feed already contains a sponsored view");
        }
        entries.add(position, adView);
        host.addView(adView);
    }

    public List<Object> getEntries() {
        return Collections.unmodifiableList(entries);
    }

    public int getProductCount() {
        return (int) entries.stream().filter(Product.class::isInstance).count();
    }

    public List<Product> search(String query) {
        String term = query.toLowerCase(Locale.ROOT);
        return entries.stream()
                .filter(Product.class::isInstance)
                .map(Product.class::cast)
                .filter(product -> product.name().toLowerCase(Locale.ROOT).contains(term)
                        || product.category().toLowerCase(Locale.ROOT).contains(term))
                .toList();
    }

    public void refresh() {
        refreshCount++;
    }

    public int getRefreshCount() {
        return refreshCount;
    }
}
