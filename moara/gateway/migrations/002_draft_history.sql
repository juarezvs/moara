ALTER TABLE moara.identity_versions DROP CONSTRAINT identity_versions_status_check;
ALTER TABLE moara.identity_versions ADD CONSTRAINT identity_versions_status_check CHECK(status IN ('draft','draft_history','active','superseded'));
ALTER TABLE moara.identity_versions ADD COLUMN parent_id uuid REFERENCES moara.identity_versions(id);
CREATE INDEX moara_identity_parent ON moara.identity_versions(parent_id);
