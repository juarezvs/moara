REVOKE TRUNCATE ON moara.legal_evidence FROM moara_app;
CREATE TRIGGER moara_legal_evidence_no_truncate BEFORE TRUNCATE ON moara.legal_evidence
 FOR EACH STATEMENT EXECUTE FUNCTION moara.prevent_audit_mutation();
