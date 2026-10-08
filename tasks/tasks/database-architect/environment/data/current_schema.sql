-- Simplified legacy model. All identifiers and values in the fixture are fictional.
CREATE TABLE tenant_registry (
    tenant_id text PRIMARY KEY,
    home_region text NOT NULL,
    service_tier text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE order_documents (
    tenant_id text NOT NULL REFERENCES tenant_registry(tenant_id),
    external_order_ref text NOT NULL,
    document jsonb NOT NULL,
    status text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, external_order_ref)
);

CREATE INDEX order_documents_status_idx
    ON order_documents (status, updated_at);

CREATE TABLE inventory_cache (
    tenant_id text NOT NULL,
    warehouse_code text NOT NULL,
    sku text NOT NULL,
    available_quantity integer NOT NULL,
    refreshed_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, warehouse_code, sku)
);

CREATE TABLE webhook_receipts (
    provider_event_id text PRIMARY KEY,
    provider text NOT NULL,
    tenant_id text NOT NULL,
    payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    processed boolean NOT NULL DEFAULT false
);

CREATE TABLE change_log (
    change_id bigserial PRIMARY KEY,
    tenant_id text NOT NULL,
    aggregate_key text NOT NULL,
    body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
