ALTER TABLE moara.document_blobs DROP CONSTRAINT IF EXISTS document_blobs_size_bytes_check;
ALTER TABLE moara.document_blobs ALTER COLUMN size_bytes TYPE bigint;
ALTER TABLE moara.document_blobs ADD CONSTRAINT document_blobs_size_bytes_check CHECK (size_bytes > 0);
CREATE TABLE IF NOT EXISTS moara.document_segments (
 resource_id uuid NOT NULL REFERENCES moara.resources(id) ON DELETE CASCADE,
 ordinal bigint NOT NULL CHECK (ordinal >= 0),
 content text NOT NULL,
 PRIMARY KEY (resource_id, ordinal)
);
GRANT SELECT,INSERT,UPDATE,DELETE ON moara.document_segments TO moara_app,moara_worker;
