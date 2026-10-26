CREATE TABLE moara.connector_tickets (
 id uuid PRIMARY KEY,token_hash char(64) UNIQUE NOT NULL,account_id uuid NOT NULL REFERENCES moara.accounts(id),
 auth_bundle text NOT NULL,profile_id varchar(64),created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz NOT NULL
);
CREATE INDEX moara_connector_ticket_expiration ON moara.connector_tickets(expires_at);
