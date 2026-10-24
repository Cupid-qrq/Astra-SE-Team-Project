CREATE TABLE feedback_catalogs (
 catalog_id uuid PRIMARY KEY,
 scope_key varchar(43) NOT NULL CHECK (scope_key = 'GLOBAL' OR scope_key ~ '^COURSE:[0-9a-f-]{36}$'),
 verdict varchar(3) NOT NULL CHECK (verdict IN ('CE','WA','TLE','RE','SE')),
 language_key varchar(7) NOT NULL CHECK (language_key IN ('ALL','cpp17','python3')),
 draft_payload jsonb NOT NULL,
 draft_revision integer NOT NULL CHECK (draft_revision > 0),
 active_version_id uuid,
 CONSTRAINT uq_feedback_scope UNIQUE (scope_key, verdict, language_key)
);
CREATE TABLE feedback_versions (
 version_id uuid PRIMARY KEY,
 catalog_id uuid NOT NULL REFERENCES feedback_catalogs(catalog_id),
 version_no integer NOT NULL CHECK (version_no > 0),
 title varchar(100) NOT NULL CHECK (length(trim(title)) > 0),
 explanation varchar(2000) NOT NULL CHECK (length(trim(explanation)) > 0),
 checklist jsonb NOT NULL CHECK (jsonb_typeof(checklist) = 'array' AND jsonb_array_length(checklist) <= 10),
 author_id uuid NOT NULL REFERENCES users(user_id),
 published_at timestamptz NOT NULL,
 checksum varchar(64) NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
 CONSTRAINT uq_feedback_version_no UNIQUE (catalog_id, version_no),
 CONSTRAINT uq_feedback_version_owner UNIQUE (catalog_id, version_id)
);
ALTER TABLE feedback_catalogs ADD CONSTRAINT fk_feedback_active
 FOREIGN KEY (catalog_id, active_version_id) REFERENCES feedback_versions(catalog_id, version_id);
CREATE INDEX ix_feedback_versions_author ON feedback_versions(author_id);
CREATE FUNCTION reject_feedback_version_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'published feedback version is immutable'; END $$;
CREATE TRIGGER immutable_feedback BEFORE UPDATE OR DELETE ON feedback_versions
 FOR EACH ROW EXECUTE FUNCTION reject_feedback_version_change();
