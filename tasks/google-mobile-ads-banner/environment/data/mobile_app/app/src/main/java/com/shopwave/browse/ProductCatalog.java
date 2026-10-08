package com.shopwave.browse;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class ProductCatalog {
    private ProductCatalog() {}

    public static List<Product> load(Path path) throws IOException {
        List<String> lines = Files.readAllLines(path, StandardCharsets.UTF_8);
        List<Product> products = new ArrayList<>();
        for (int index = 1; index < lines.size(); index++) {
            String line = lines.get(index).trim();
            if (line.isEmpty()) {
                continue;
            }
            String[] values = line.split(",", -1);
            if (values.length != 5) {
                throw new IOException("Malformed catalog row " + (index + 1));
            }
            products.add(new Product(
                    values[0], values[1], values[2], Integer.parseInt(values[3]),
                    Boolean.parseBoolean(values[4])));
        }
        return products;
    }
}
