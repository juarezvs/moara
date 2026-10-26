CREATE TABLE moara.resources (
 id uuid PRIMARY KEY, kind varchar(30) NOT NULL CHECK(kind IN ('document','prompt','template','assistant','project','case','workflow','dashboard')),
 owner_id uuid NOT NULL REFERENCES moara.accounts(id), group_id uuid REFERENCES moara.groups(id),
 title varchar(200) NOT NULL, body text NOT NULL, version integer NOT NULL DEFAULT 1 CHECK(version>0),
 archived boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX moara_resources_owner ON moara.resources(owner_id,kind,updated_at DESC);
CREATE INDEX moara_resources_group ON moara.resources(group_id,kind) WHERE NOT archived;
CREATE TABLE moara.resource_versions (
 resource_id uuid NOT NULL REFERENCES moara.resources(id), version integer NOT NULL, body text NOT NULL,
 title varchar(200) NOT NULL, author_id uuid NOT NULL REFERENCES moara.accounts(id), created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(resource_id,version)
);
CREATE TABLE moara.document_blobs (
 resource_id uuid PRIMARY KEY REFERENCES moara.resources(id), content text NOT NULL, sha256 char(64) NOT NULL,
 filename varchar(180) NOT NULL, media_type varchar(100) NOT NULL, size_bytes integer NOT NULL CHECK(size_bytes BETWEEN 1 AND 4194304)
);
CREATE TABLE moara.document_chunks (
 id uuid PRIMARY KEY, document_id uuid NOT NULL REFERENCES moara.resources(id), ordinal integer NOT NULL,
 page integer, content text NOT NULL, search_terms tsvector NOT NULL, embedding vector(768) NOT NULL,
 embedding_model varchar(120) NOT NULL, checksum char(64) NOT NULL,
 UNIQUE(document_id,ordinal)
);
CREATE INDEX moara_chunk_document ON moara.document_chunks(document_id);
CREATE INDEX moara_chunk_terms ON moara.document_chunks USING gin(search_terms);
CREATE TABLE moara.platform_runs (
 id uuid PRIMARY KEY, resource_id uuid REFERENCES moara.resources(id), account_id uuid NOT NULL REFERENCES moara.accounts(id),
 api_key_id uuid REFERENCES moara.api_keys(id), kind varchar(40) NOT NULL,
 status varchar(20) NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled','awaiting_approval')),
 payload text NOT NULL, result text, source_ids jsonb NOT NULL DEFAULT '[]',
 payload_hash char(64) NOT NULL, idempotency_key varchar(100), error_code varchar(80), cancel_requested boolean NOT NULL DEFAULT false,
 lease_until timestamptz, created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
 updated_at timestamptz NOT NULL DEFAULT now(), attempts integer NOT NULL DEFAULT 0,
 approval_digest char(64), approved_by uuid REFERENCES moara.accounts(id), approved_at timestamptz
);
CREATE UNIQUE INDEX moara_platform_idempotency ON moara.platform_runs(account_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX moara_platform_queue ON moara.platform_runs(status,created_at);
CREATE TABLE moara.flow_schedules (
 resource_id uuid PRIMARY KEY REFERENCES moara.resources(id), enabled boolean NOT NULL DEFAULT false,
 interval_seconds integer NOT NULL CHECK(interval_seconds BETWEEN 300 AND 2592000),
 next_run timestamptz NOT NULL DEFAULT now(), last_run uuid REFERENCES moara.platform_runs(id)
);
CREATE TABLE moara.phase_evidence (
 id uuid PRIMARY KEY, phase integer NOT NULL CHECK(phase BETWEEN 0 AND 13),
 name varchar(160) NOT NULL, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
REVOKE UPDATE,DELETE ON moara.audit FROM moara_app;
CREATE FUNCTION moara.prevent_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Audit records are append-only'; END $$;
CREATE TRIGGER moara_audit_append_only BEFORE UPDATE OR DELETE ON moara.audit
 FOR EACH ROW EXECUTE FUNCTION moara.prevent_audit_mutation();
UPDATE moara.roles SET permissions=permissions || '["workspace.use","knowledge.use","documents.use","development.use","workflows.use"]'::jsonb
 WHERE builtin AND id IN ('user','analyst','manager','ai_administrator','connector_administrator')
 AND NOT permissions ? 'workspace.use';
