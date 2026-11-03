CREATE TABLE moara.official_assistants (
 id varchar(32) PRIMARY KEY,
 revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
 definition jsonb NOT NULL,
 sha256 char(64) NOT NULL,
 updated_by varchar(200) NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE moara.official_assistant_versions (
 assistant_id varchar(32) NOT NULL REFERENCES moara.official_assistants(id),
 revision integer NOT NULL CHECK(revision>0), definition jsonb NOT NULL,sha256 char(64) NOT NULL,
 author varchar(200) NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(assistant_id,revision)
);
GRANT SELECT,INSERT,UPDATE ON moara.official_assistants TO moara_app;
REVOKE DELETE,TRUNCATE ON moara.official_assistants FROM moara_app;
GRANT SELECT,INSERT ON moara.official_assistant_versions TO moara_app;
REVOKE UPDATE,DELETE,TRUNCATE ON moara.official_assistant_versions FROM moara_app;
CREATE TRIGGER moara_assistant_versions_append_only BEFORE UPDATE OR DELETE ON moara.official_assistant_versions
 FOR EACH ROW EXECUTE FUNCTION moara.prevent_audit_mutation();
CREATE TRIGGER moara_assistant_versions_no_truncate BEFORE TRUNCATE ON moara.official_assistant_versions
 FOR EACH STATEMENT EXECUTE FUNCTION moara.prevent_audit_mutation();
