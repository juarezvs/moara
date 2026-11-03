-- Zero is an explicit administrative exemption, not a larger finite quota.
ALTER TABLE moara.api_keys DROP CONSTRAINT api_keys_rpm_check;
ALTER TABLE moara.api_keys ADD CONSTRAINT api_keys_rpm_check CHECK(rpm BETWEEN 0 AND 600);
COMMENT ON COLUMN moara.api_keys.rpm IS 'Requests per minute; 0 means no per-key request quota. Authentication, scopes and resource capacity still apply.';
