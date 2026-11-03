CREATE TABLE moara.legal_evidence (
 id uuid PRIMARY KEY,
 account_id uuid NOT NULL REFERENCES moara.accounts(id),
 api_key_id uuid REFERENCES moara.api_keys(id),
 manifest text NOT NULL,
 sha256 char(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX moara_legal_evidence_owner ON moara.legal_evidence(account_id,created_at DESC);
REVOKE UPDATE, DELETE ON moara.legal_evidence FROM moara_app;
GRANT SELECT, INSERT ON moara.legal_evidence TO moara_app;
CREATE TRIGGER moara_legal_evidence_append_only BEFORE UPDATE OR DELETE ON moara.legal_evidence
 FOR EACH ROW EXECUTE FUNCTION moara.prevent_audit_mutation();
