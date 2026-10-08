CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('pdf', 'csv')),
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    source_url TEXT,
    published_on TEXT,
    data_kind TEXT NOT NULL CHECK (data_kind IN ('fact', 'demo')),
    page_count INTEGER,
    extraction_status TEXT NOT NULL CHECK (extraction_status IN ('ready', 'needs_ocr')),
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_chunks (
    evidence_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id),
    locator TEXT NOT NULL,
    pdf_page INTEGER,
    csv_row INTEGER,
    text TEXT NOT NULL,
    supporting_document_id TEXT REFERENCES documents(document_id),
    supporting_pdf_page INTEGER,
    UNIQUE(document_id, locator),
    CHECK ((pdf_page IS NOT NULL AND csv_row IS NULL AND pdf_page >= 1)
        OR (pdf_page IS NULL AND csv_row IS NOT NULL AND csv_row >= 2)),
    CHECK ((supporting_document_id IS NULL AND supporting_pdf_page IS NULL)
        OR (supporting_document_id IS NOT NULL AND supporting_pdf_page IS NOT NULL AND supporting_pdf_page >= 1))
);
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('company', 'material', 'product', 'process')),
    name TEXT NOT NULL,
    grade TEXT NOT NULL DEFAULT '',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    verification_status TEXT NOT NULL CHECK (verification_status IN ('pending', 'verified')),
    evidence_id TEXT NOT NULL REFERENCES evidence_chunks(evidence_id)
);
CREATE TABLE IF NOT EXISTS companies (
    company_id TEXT PRIMARY KEY REFERENCES entities(entity_id),
    security_code TEXT,
    industry_stage TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relations (
    relation_id TEXT PRIMARY KEY,
    upstream_id TEXT NOT NULL REFERENCES entities(entity_id),
    downstream_id TEXT NOT NULL REFERENCES entities(entity_id),
    relation_type TEXT NOT NULL,
    material_grade TEXT NOT NULL DEFAULT '',
    valid_from TEXT,
    valid_to TEXT,
    verification_status TEXT NOT NULL CHECK (verification_status IN ('pending', 'verified')),
    evidence_id TEXT NOT NULL REFERENCES evidence_chunks(evidence_id),
    CHECK (upstream_id != downstream_id)
);
CREATE TABLE IF NOT EXISTS prices (
    price_id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES entities(entity_id),
    grade TEXT NOT NULL,
    date TEXT NOT NULL,
    price TEXT NOT NULL,
    unit TEXT NOT NULL,
    currency TEXT NOT NULL,
    price_basis TEXT NOT NULL,
    value_type TEXT NOT NULL CHECK (value_type IN ('fact', 'estimate', 'scenario')),
    assumption_note TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL CHECK (verification_status IN ('pending', 'verified')),
    evidence_id TEXT NOT NULL REFERENCES evidence_chunks(evidence_id)
);
CREATE TABLE IF NOT EXISTS parameters (
    parameter_id TEXT PRIMARY KEY,
    company_id TEXT REFERENCES companies(company_id),
    product_id TEXT REFERENCES entities(entity_id),
    parameter_name TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT NOT NULL,
    period TEXT NOT NULL,
    value_type TEXT NOT NULL CHECK (value_type IN ('fact', 'estimate', 'scenario')),
    assumption_note TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL CHECK (verification_status IN ('pending', 'verified')),
    evidence_id TEXT NOT NULL REFERENCES evidence_chunks(evidence_id)
);
CREATE TABLE IF NOT EXISTS metrics (
    metric_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(company_id),
    metric_name TEXT NOT NULL,
    period TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT NOT NULL,
    currency TEXT NOT NULL,
    value_type TEXT NOT NULL CHECK (value_type IN ('fact', 'estimate', 'scenario')),
    assumption_note TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL CHECK (verification_status IN ('pending', 'verified')),
    evidence_id TEXT NOT NULL REFERENCES evidence_chunks(evidence_id)
);
CREATE INDEX IF NOT EXISTS idx_evidence_document ON evidence_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_relations_upstream ON relations(upstream_id);
CREATE INDEX IF NOT EXISTS idx_prices_material_date ON prices(material_id, date);
