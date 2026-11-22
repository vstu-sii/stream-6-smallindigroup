BEGIN;

CREATE TABLE review_batches (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE products (
    platform text NOT NULL CHECK (platform IN ('wildberries', 'ozon', 'yandex_market')),
    external_id text NOT NULL CHECK (btrim(external_id) <> ''),
    PRIMARY KEY (platform, external_id)
);

CREATE TABLE reviews (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform text NOT NULL,
    product_external_id text NOT NULL,
    external_id text NOT NULL CHECK (btrim(external_id) <> ''),
    FOREIGN KEY (platform, product_external_id) REFERENCES products (platform, external_id),
    UNIQUE (platform, external_id),
    UNIQUE (id, platform, product_external_id)
);

CREATE TABLE batch_reviews (
    batch_id bigint NOT NULL REFERENCES review_batches (id),
    review_id bigint NOT NULL,
    platform text NOT NULL,
    product_external_id text NOT NULL,
    rating smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    body text NOT NULL CHECK (btrim(body) <> ''),
    published_on date,
    suspicious boolean,
    PRIMARY KEY (batch_id, review_id),
    UNIQUE (batch_id, review_id, platform, product_external_id),
    FOREIGN KEY (review_id, platform, product_external_id)
        REFERENCES reviews (id, platform, product_external_id)
);

CREATE TABLE analysis_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id bigint NOT NULL UNIQUE REFERENCES review_batches (id),
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'partial', 'failed')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    lease_until timestamptz,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, batch_id),
    CHECK ((status = 'running') = (lease_until IS NOT NULL)),
    CHECK (status <> 'failed' OR error_code IS NOT NULL),
    CHECK (error_code IS NULL OR status IN ('partial', 'failed'))
);

CREATE INDEX analysis_runs_ready_idx ON analysis_runs (status, created_at)
    WHERE status IN ('queued', 'running');

CREATE TABLE problem_groups (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL,
    batch_id bigint NOT NULL,
    platform text NOT NULL,
    product_external_id text NOT NULL,
    problem_code text NOT NULL CHECK (btrim(problem_code) <> ''),
    title text NOT NULL CHECK (btrim(title) <> ''),
    severity text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    priority integer NOT NULL CHECK (priority > 0),
    owner text CHECK (owner IN ('seller', 'marketplace')),
    recommendation text NOT NULL CHECK (btrim(recommendation) <> ''),
    FOREIGN KEY (run_id, batch_id) REFERENCES analysis_runs (id, batch_id),
    FOREIGN KEY (platform, product_external_id) REFERENCES products (platform, external_id),
    UNIQUE (run_id, platform, product_external_id, problem_code),
    UNIQUE (id, batch_id, platform, product_external_id)
);

CREATE TABLE problem_evidence (
    group_id bigint NOT NULL,
    review_id bigint NOT NULL,
    batch_id bigint NOT NULL,
    platform text NOT NULL,
    product_external_id text NOT NULL,
    start_offset integer NOT NULL CHECK (start_offset >= 0),
    end_offset integer NOT NULL CHECK (end_offset > start_offset),
    excerpt text NOT NULL CHECK (btrim(excerpt) <> ''),
    PRIMARY KEY (group_id, review_id, start_offset, end_offset),
    FOREIGN KEY (group_id, batch_id, platform, product_external_id)
        REFERENCES problem_groups (id, batch_id, platform, product_external_id),
    FOREIGN KEY (batch_id, review_id, platform, product_external_id)
        REFERENCES batch_reviews (batch_id, review_id, platform, product_external_id)
);

CREATE INDEX batch_reviews_product_idx ON batch_reviews (batch_id, platform, product_external_id);

COMMIT;
