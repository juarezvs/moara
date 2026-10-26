ALTER TABLE moara.jobs ADD COLUMN lease_until timestamptz;
ALTER TABLE moara.jobs ADD COLUMN attempts integer NOT NULL DEFAULT 0;
CREATE TABLE moara.embedding_indexes (
 id uuid PRIMARY KEY,model_id uuid NOT NULL REFERENCES moara.models(id),binding_id uuid NOT NULL REFERENCES moara.execution_bindings(id),
 dimension integer NOT NULL CHECK(dimension BETWEEN 32 AND 8192),digest varchar(100) NOT NULL,
 active boolean NOT NULL DEFAULT false,created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(model_id,digest)
);
