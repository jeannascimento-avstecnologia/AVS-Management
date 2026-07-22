-- hub_v1.sql — Schema SQLite hub.db (ADR-0002)
-- Smoke: sqlite3 :memory: < docs/hub/schema/hub_v1.sql
-- Bootstrap app: PRAGMA foreign_keys = ON (obrigatório em cada conexão)
-- Path runtime: HUB_DB_PATH (default data/hub.db) — P0.4

PRAGMA foreign_keys = ON;

-- =============================================================================
-- 1. quotes
-- status: draft | submitted | sent | approved | rejected | contracted
-- billed_by_type: distribuidor | fornecedor
-- lead_temperature: coluna FF (filtro UI = O3)
-- =============================================================================
CREATE TABLE quotes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj                    TEXT    NOT NULL
                            CHECK (length(cnpj) = 14 AND cnpj GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
    client_name             TEXT,
    tiflux_client_id        INTEGER,
    vhsys_client_id         INTEGER,
    status                  TEXT    NOT NULL
                            CHECK (status IN (
                                'draft', 'submitted', 'sent',
                                'approved', 'rejected', 'contracted'
                            )),
    lead_temperature        TEXT,   -- FF: quente|morno|frio (filtro UI = O3)
    billed_by_type          TEXT
                            CHECK (billed_by_type IS NULL
                                OR billed_by_type IN ('distribuidor', 'fornecedor')),
    billed_by_name          TEXT,
    implant_payment_plan    TEXT,
    implant_discount_pct    REAL,
    implant_discount_value  REAL,
    implant_labor_hours     REAL,
    implant_labor_hourly_rate REAL,
    monthly_payment_plan    TEXT,
    monthly_discount_pct    REAL,
    monthly_discount_value  REAL,
    monthly_labor_hours     REAL,
    monthly_labor_hourly_rate REAL,
    modules_json            TEXT,   -- JSON array QuoteModule (SoT passo 2 / PDF)
    client_email            TEXT,   -- e-mail principal (envio orçamento)
    extra_recipients        TEXT,   -- JSON array de e-mails extras (CC)
    notes                   TEXT,   -- observações do PDF / wizard passo 3
    tiflux_ticket_number    TEXT,
    vhsys_os_id             TEXT,
    pdf_path                TEXT,   -- UUID filename; fora web root
    created_by              INTEGER, -- user id auth (lógico)
    created_at              TEXT    NOT NULL,
    updated_at              TEXT    NOT NULL,
    submitted_at            TEXT,
    sent_at                 TEXT,
    approved_at             TEXT
);

CREATE INDEX idx_quotes_status ON quotes (status);
CREATE INDEX idx_quotes_cnpj ON quotes (cnpj);

-- =============================================================================
-- 2. quote_items
-- section: module.id (texto livre; seed implantacao|mensalidade + custom)
-- =============================================================================
CREATE TABLE quote_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id        INTEGER NOT NULL
                    REFERENCES quotes (id) ON DELETE CASCADE,
    section         TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    qty             REAL    NOT NULL DEFAULT 1,
    unit_value      REAL    NOT NULL DEFAULT 0,
    total_value     REAL    NOT NULL, -- qty * unit (app calcula; DB armazena)
    template_key    TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_quote_items_quote_section_sort
    ON quote_items (quote_id, section, sort_order);

-- =============================================================================
-- 3. quote_templates
-- section: module.id (texto livre; seed + custom)
-- lines_json: JSON array [{ "name", "qty", "unit_value", "sort_order" }]
-- =============================================================================
CREATE TABLE quote_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    section     TEXT    NOT NULL,
    lines_json  TEXT    NOT NULL, -- JSON array de linhas default (ADR-0002)
    created_at  TEXT    NOT NULL
);

-- =============================================================================
-- 3b. quote_module_templates
-- Catálogo de blocos reutilizáveis (não inclui Implantação/Mensalidade).
-- lines_json: JSON array [{ "name", "qty", "unit_value", "sort_order" }] (pode ser [])
-- =============================================================================
CREATE TABLE quote_module_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    show_labor  INTEGER NOT NULL DEFAULT 0
                CHECK (show_labor IN (0, 1)),
    lines_json  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

-- =============================================================================
-- 4. billing_runs
-- status: draft | approved | awaiting_prefeitura | emitting | sent | error
-- payment_method: boleto | pix
-- competence: YYYY-MM
-- =============================================================================
CREATE TABLE billing_runs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj                    TEXT    NOT NULL
                            CHECK (length(cnpj) = 14 AND cnpj GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
    client_name             TEXT,
    tiflux_client_id        INTEGER,
    vhsys_client_id         INTEGER,
    competence              TEXT    NOT NULL
                            CHECK (competence GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    due_date                TEXT,   -- ISO date YYYY-MM-DD
    status                  TEXT    NOT NULL
                            CHECK (status IN (
                                'draft', 'approved', 'awaiting_prefeitura',
                                'emitting', 'sent', 'error'
                            )),
    has_retencao            INTEGER NOT NULL DEFAULT 0
                            CHECK (has_retencao IN (0, 1)),
    payment_method          TEXT
                            CHECK (payment_method IS NULL
                                OR payment_method IN ('boleto', 'pix')),
    gross_total             REAL,
    discount_pct            REAL,   -- % sobre bruto
    discount_value          REAL,   -- R$ fixo após %
    net_total               REAL,   -- líquido (após desconto; retenção sobrescreve)
    nf_prefeitura_number    TEXT,   -- branch humana
    tiflux_ticket_number    TEXT,
    vhsys_nf_id             TEXT,
    vhsys_cr_id             TEXT,
    error_message           TEXT,
    approved_by             INTEGER, -- user id auth
    created_by              INTEGER,
    created_at              TEXT    NOT NULL,
    updated_at              TEXT    NOT NULL,
    approved_at             TEXT,
    sent_at                 TEXT
);

CREATE INDEX idx_billing_runs_status ON billing_runs (status);
CREATE INDEX idx_billing_runs_competence ON billing_runs (competence);
CREATE INDEX idx_billing_runs_cnpj ON billing_runs (cnpj);
CREATE INDEX idx_billing_runs_tiflux_client ON billing_runs (tiflux_client_id);

-- Evita duplicar fila do mês por cliente TiFlux (ADR-0002 UNIQUE parcial)
CREATE UNIQUE INDEX uq_billing_runs_tiflux_competence
    ON billing_runs (tiflux_client_id, competence)
    WHERE tiflux_client_id IS NOT NULL;

-- =============================================================================
-- 5. billing_items
-- source: contract | ticket
-- =============================================================================
CREATE TABLE billing_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL
                    REFERENCES billing_runs (id) ON DELETE CASCADE,
    source          TEXT    NOT NULL
                    CHECK (source IN ('contract', 'ticket')),
    external_ref    TEXT,   -- id contrato/ticket TiFlux
    description     TEXT    NOT NULL,
    amount          REAL    NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_billing_items_run_sort ON billing_items (run_id, sort_order);

-- =============================================================================
-- 6. billing_artifacts
-- kind: report | nf | boleto
-- =============================================================================
CREATE TABLE billing_artifacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL
                    REFERENCES billing_runs (id) ON DELETE CASCADE,
    kind            TEXT    NOT NULL
                    CHECK (kind IN ('report', 'nf', 'boleto')),
    path_or_url     TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE INDEX idx_billing_artifacts_run ON billing_artifacts (run_id);

-- =============================================================================
-- 7. webhook_outbox
-- status: pending | sent | acked | error  (fluxo: pending→sent→acked|error)
-- event: quote.submit | quote.sent | quote.approved
--        | billing.approved | billing.nf_prefeitura  (ADR-0003)
-- payload_json: envelope OutboxEvent (ADR-0002/0003)
-- =============================================================================
CREATE TABLE webhook_outbox (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event               TEXT    NOT NULL
                        CHECK (event IN (
                            'quote.submit', 'quote.sent', 'quote.approved',
                            'billing.approved', 'billing.nf_prefeitura'
                        )),
    payload_json        TEXT    NOT NULL,
    status              TEXT    NOT NULL
                        CHECK (status IN ('pending', 'sent', 'acked', 'error')),
    attempts            INTEGER NOT NULL DEFAULT 0,
    last_error          TEXT,
    idempotency_key     TEXT    UNIQUE, -- ex. quote.submit:quote:42
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL,
    acked_at            TEXT
);

CREATE INDEX idx_webhook_outbox_status_created
    ON webhook_outbox (status, created_at);
