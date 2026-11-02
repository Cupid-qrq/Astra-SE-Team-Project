CREATE TABLE template_catalogs (
 template_id uuid PRIMARY KEY,
 scope_key varchar(43) NOT NULL CHECK (scope_key = 'GLOBAL' OR scope_key ~ '^COURSE:[0-9a-f-]{36}$'),
 draft_payload jsonb NOT NULL,
 draft_revision integer NOT NULL CHECK (draft_revision > 0),
 published_version_id uuid,
 active_version_id uuid,
 CONSTRAINT uq_template_scope UNIQUE (scope_key)
);
CREATE TABLE template_versions (
 version_id uuid PRIMARY KEY,
 template_id uuid NOT NULL REFERENCES template_catalogs(template_id),
 version_no integer NOT NULL CHECK (version_no > 0),
 body text NOT NULL CHECK (octet_length(body) BETWEEN 1 AND 8192),
 allowed_placeholders jsonb NOT NULL CHECK (jsonb_typeof(allowed_placeholders) = 'array' AND jsonb_array_length(allowed_placeholders) <= 6),
 schema_version varchar(40) NOT NULL CHECK (length(trim(schema_version)) > 0),
 author_id uuid NOT NULL REFERENCES users(user_id),
 published_at timestamptz(3) NOT NULL,
 checksum varchar(64) NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
 CONSTRAINT uq_template_version_no UNIQUE (template_id, version_no),
 CONSTRAINT uq_template_version_owner UNIQUE (template_id, version_id)
);
ALTER TABLE template_catalogs ADD CONSTRAINT fk_template_published
 FOREIGN KEY (template_id, published_version_id) REFERENCES template_versions(template_id, version_id);
ALTER TABLE template_catalogs ADD CONSTRAINT fk_template_active
 FOREIGN KEY (template_id, active_version_id) REFERENCES template_versions(template_id, version_id);
CREATE FUNCTION reject_template_version_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'published template version is immutable'; END $$;
CREATE TRIGGER immutable_template BEFORE UPDATE OR DELETE ON template_versions
 FOR EACH ROW EXECUTE FUNCTION reject_template_version_change();
