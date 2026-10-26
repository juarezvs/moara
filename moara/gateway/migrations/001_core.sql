-- The dedicated schema is provisioned by the deployment operator. The
-- migrator owns this schema, without permission to create other schemas.
CREATE TABLE moara.accounts (
 id uuid PRIMARY KEY, subject varchar(130) UNIQUE NOT NULL, name varchar(160) NOT NULL,
 email varchar(200), auth_source varchar(20) NOT NULL CHECK(auth_source IN ('legacy','local','integration')),
 legacy_id uuid UNIQUE, password_hash text, password_change_required boolean NOT NULL DEFAULT false,
 active boolean NOT NULL DEFAULT true, session_version integer NOT NULL DEFAULT 1,
 preferences jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX moara_local_email ON moara.accounts(lower(email)) WHERE auth_source='local';
CREATE TABLE moara.roles (id varchar(50) PRIMARY KEY,name varchar(100) NOT NULL,permissions jsonb NOT NULL,builtin boolean NOT NULL DEFAULT false);
CREATE TABLE moara.account_roles (account_id uuid REFERENCES moara.accounts(id),role_id varchar(50) REFERENCES moara.roles(id),PRIMARY KEY(account_id,role_id));
CREATE TABLE moara.groups (id uuid PRIMARY KEY,name varchar(120) NOT NULL UNIQUE);
CREATE TABLE moara.group_members (group_id uuid REFERENCES moara.groups(id) ON DELETE CASCADE,account_id uuid REFERENCES moara.accounts(id),PRIMARY KEY(group_id,account_id));
CREATE TABLE moara.sessions (
 id uuid PRIMARY KEY,account_id uuid NOT NULL REFERENCES moara.accounts(id),token_hash char(64) UNIQUE NOT NULL,
 session_version integer NOT NULL,legacy_token text,legacy_checked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz NOT NULL,revoked_at timestamptz
);
CREATE INDEX moara_sessions_account ON moara.sessions(account_id);
CREATE TABLE moara.api_keys (
 id uuid PRIMARY KEY,account_id uuid NOT NULL REFERENCES moara.accounts(id),name varchar(120) NOT NULL,
 token_hash char(64) UNIQUE NOT NULL,scopes jsonb NOT NULL,rpm integer NOT NULL DEFAULT 60 CHECK(rpm BETWEEN 1 AND 600),allowed_profiles jsonb NOT NULL DEFAULT '[]',
 allowed_sources jsonb NOT NULL DEFAULT '[]',created_by uuid REFERENCES moara.accounts(id),
 created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz,revoked_at timestamptz,last_used_at timestamptz
);
CREATE TABLE moara.identity_versions (
 id uuid PRIMARY KEY,version varchar(80) NOT NULL,body jsonb NOT NULL,sha256 char(64) NOT NULL,
 status varchar(20) NOT NULL CHECK(status IN ('draft','active','superseded')),
 created_by varchar(130) NOT NULL,approved_by varchar(130),approval_source varchar(80),restored_from uuid,
 created_at timestamptz NOT NULL DEFAULT now(),published_at timestamptz
);
CREATE UNIQUE INDEX moara_one_active_identity ON moara.identity_versions(status) WHERE status='active';
CREATE FUNCTION moara.immutable_published_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status <> 'draft' AND (NEW.body IS DISTINCT FROM OLD.body OR NEW.sha256 <> OLD.sha256 OR NEW.version <> OLD.version) THEN
  RAISE EXCEPTION 'Published institutional identity content is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER moara_identity_content_guard BEFORE UPDATE ON moara.identity_versions FOR EACH ROW EXECUTE FUNCTION moara.immutable_published_identity();
CREATE TABLE moara.models (
 id uuid PRIMARY KEY,provider varchar(40) NOT NULL,tag varchar(180) NOT NULL,display_name varchar(180) NOT NULL,
 family varchar(80),parameter_size varchar(40),quantization varchar(40),size_bytes bigint,digest varchar(100),
 declared_context integer,capabilities jsonb NOT NULL DEFAULT '{}',settings jsonb NOT NULL DEFAULT '{}',
 installed boolean NOT NULL DEFAULT true,enabled boolean NOT NULL DEFAULT true,protected boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),UNIQUE(provider,tag)
);
CREATE TABLE moara.profiles (
 id varchar(64) PRIMARY KEY,name varchar(120) NOT NULL,description varchar(1200) NOT NULL DEFAULT '',
 category varchar(40) NOT NULL DEFAULT 'general',enabled boolean NOT NULL DEFAULT true,manual_allowed boolean NOT NULL DEFAULT true,
 public boolean NOT NULL DEFAULT false,allowed_subjects jsonb NOT NULL DEFAULT '[]',allowed_groups jsonb NOT NULL DEFAULT '[]',
 settings jsonb NOT NULL DEFAULT '{}',legacy_compatible boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE moara.execution_bindings (
 id uuid PRIMARY KEY,model_id uuid NOT NULL REFERENCES moara.models(id),provider varchar(40) NOT NULL,
 tag varchar(180) NOT NULL,context_length integer NOT NULL,threads integer NOT NULL,
 ready boolean NOT NULL DEFAULT false,legacy_alias varchar(128),created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(model_id,context_length,threads)
);
CREATE TABLE moara.profile_models (
 profile_id varchar(64) REFERENCES moara.profiles(id) ON DELETE CASCADE,model_id uuid REFERENCES moara.models(id),
 priority integer NOT NULL DEFAULT 0,PRIMARY KEY(profile_id,model_id)
);
CREATE TABLE moara.jobs (
 id uuid PRIMARY KEY,account_id uuid NOT NULL REFERENCES moara.accounts(id),api_key_id uuid REFERENCES moara.api_keys(id),
 kind varchar(40) NOT NULL,status varchar(20) NOT NULL DEFAULT 'queued',payload text NOT NULL,result text,
 error_code varchar(80),progress integer NOT NULL DEFAULT 0,cancel_requested boolean NOT NULL DEFAULT false,
 idempotency_key varchar(100),payload_hash char(64) NOT NULL,dispatched_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,updated_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz
);
CREATE UNIQUE INDEX moara_job_idempotency ON moara.jobs(account_id,kind,idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX moara_jobs_queue ON moara.jobs(status,created_at);
CREATE TABLE moara.benchmark_samples (
 id bigserial PRIMARY KEY,job_id uuid NOT NULL REFERENCES moara.jobs(id),model_id uuid NOT NULL REFERENCES moara.models(id),
 parameters jsonb NOT NULL,metrics jsonb NOT NULL,quality jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE moara.requests (
 id uuid PRIMARY KEY,account_id uuid REFERENCES moara.accounts(id),api_key_id uuid REFERENCES moara.api_keys(id),
 profile_id varchar(64),model_id uuid REFERENCES moara.models(id),routing_reason varchar(500),
 status varchar(30) NOT NULL,stream boolean NOT NULL,identity_version varchar(80),duration_ms integer,ttft_ms integer,
 prompt_tokens integer,completion_tokens integer,error_code varchar(80),created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX moara_requests_metrics ON moara.requests(model_id,created_at);
CREATE TABLE moara.audit (
 id bigserial PRIMARY KEY,actor_subject varchar(130) NOT NULL,api_key_id uuid,
 action varchar(100) NOT NULL,resource varchar(160),status varchar(30) NOT NULL,
 error_code varchar(80),request_id uuid,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX moara_audit_created ON moara.audit(created_at);
CREATE TABLE moara.chat_folders (id uuid PRIMARY KEY,account_id uuid REFERENCES moara.accounts(id),name varchar(120) NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE moara.chats (
 id uuid PRIMARY KEY,account_id uuid NOT NULL REFERENCES moara.accounts(id),title varchar(200) NOT NULL DEFAULT 'Novo chat',
 profile_id varchar(64) NOT NULL DEFAULT 'auto',folder_id uuid REFERENCES moara.chat_folders(id) ON DELETE SET NULL,
 pinned boolean NOT NULL DEFAULT false,archived boolean NOT NULL DEFAULT false,legacy_id varchar(120),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX moara_chats_owner ON moara.chats(account_id,updated_at);
CREATE TABLE moara.messages (
 id uuid PRIMARY KEY,chat_id uuid NOT NULL REFERENCES moara.chats(id) ON DELETE CASCADE,
 role varchar(20) NOT NULL CHECK(role IN ('user','assistant','tool')),content text NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}',status varchar(20) NOT NULL DEFAULT 'completed',created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX moara_messages_chat ON moara.messages(chat_id,created_at);
