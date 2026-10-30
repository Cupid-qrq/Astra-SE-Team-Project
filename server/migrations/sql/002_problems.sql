
CREATE TABLE problem_families (
	canonical_problem_id UUID NOT NULL,
	owner_teacher_id UUID NOT NULL,
	label VARCHAR(100) NOT NULL,
	CONSTRAINT pk_problem_families PRIMARY KEY (canonical_problem_id),
	CONSTRAINT fk_problem_families_owner_teacher_id_users FOREIGN KEY(owner_teacher_id) REFERENCES users (user_id)
)

;

CREATE TABLE problems (
	problem_id UUID NOT NULL,
	canonical_problem_id UUID NOT NULL,
	owner_course_id UUID NOT NULL,
	practice_released BOOLEAN NOT NULL,
	practice_version_id UUID,
	revision INTEGER NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_problems PRIMARY KEY (problem_id),
	CONSTRAINT ck_problems_revision CHECK (revision > 0),
	CONSTRAINT ck_problems_practice_version CHECK (NOT practice_released OR practice_version_id IS NOT NULL),
	CONSTRAINT fk_problems_canonical_problem_id_problem_families FOREIGN KEY(canonical_problem_id) REFERENCES problem_families (canonical_problem_id),
	CONSTRAINT fk_problems_owner_course_id_courses FOREIGN KEY(owner_course_id) REFERENCES courses (course_id)
)

;
CREATE INDEX ix_problems_course ON problems (owner_course_id);
CREATE INDEX ix_problems_family ON problems (canonical_problem_id);

CREATE TABLE problem_versions (
	version_id UUID NOT NULL,
	problem_id UUID NOT NULL,
	version_no INTEGER NOT NULL,
	title VARCHAR(100) NOT NULL,
	statement TEXT NOT NULL,
	samples JSONB NOT NULL,
	tags JSONB NOT NULL,
	profile JSONB NOT NULL,
	source_ref VARCHAR(500) NOT NULL,
	checksum VARCHAR(64),
	published_at TIMESTAMP(3) WITH TIME ZONE,
	revision INTEGER NOT NULL,
	published_preflight_id UUID,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_problem_versions PRIMARY KEY (version_id),
	CONSTRAINT uq_problem_versions_problem_id UNIQUE (problem_id, version_no),
	CONSTRAINT uq_problem_versions_problem_version UNIQUE (problem_id, version_id),
	CONSTRAINT ck_problem_versions_revision CHECK (revision > 0 AND version_no > 0),
	CONSTRAINT ck_problem_versions_statement_bytes CHECK (octet_length(statement) BETWEEN 1 AND 32768),
	CONSTRAINT ck_problem_versions_samples_count CHECK (jsonb_array_length(samples) BETWEEN 1 AND 3),
	CONSTRAINT ck_problem_versions_tags_count CHECK (jsonb_array_length(tags) <= 5),
	CONSTRAINT ck_problem_versions_publication CHECK ((published_at IS NULL) = (checksum IS NULL)),
	CONSTRAINT fk_problem_versions_problem_id_problems FOREIGN KEY(problem_id) REFERENCES problems (problem_id)
)

;

CREATE TABLE reference_programs (
	reference_id UUID NOT NULL,
	version_id UUID NOT NULL,
	language_key VARCHAR(10) NOT NULL,
	code BYTEA NOT NULL,
	code_sha256 VARCHAR(64) NOT NULL,
	CONSTRAINT pk_reference_programs PRIMARY KEY (reference_id),
	CONSTRAINT uq_reference_programs_version_id UNIQUE (version_id, language_key),
	CONSTRAINT ck_reference_programs_language CHECK (language_key IN ('cpp17','python3')),
	CONSTRAINT ck_reference_programs_bytes CHECK (octet_length(code) BETWEEN 1 AND 65536),
	CONSTRAINT fk_reference_programs_version_id_problem_versions FOREIGN KEY(version_id) REFERENCES problem_versions (version_id)
)

;

CREATE TABLE testcases (
	testcase_id UUID NOT NULL,
	version_id UUID NOT NULL,
	"order" INTEGER NOT NULL,
	input_blob BYTEA NOT NULL,
	answer_blob BYTEA NOT NULL,
	input_sha256 VARCHAR(64) NOT NULL,
	answer_sha256 VARCHAR(64) NOT NULL,
	CONSTRAINT pk_testcases PRIMARY KEY (testcase_id),
	CONSTRAINT uq_testcases_version_id UNIQUE (version_id, "order"),
	CONSTRAINT ck_testcases_order_range CHECK ("order" BETWEEN 1 AND 10),
	CONSTRAINT ck_testcases_bytes CHECK (octet_length(input_blob) <= 65536 AND octet_length(answer_blob) <= 65536),
	CONSTRAINT fk_testcases_version_id_problem_versions FOREIGN KEY(version_id) REFERENCES problem_versions (version_id)
)

;
ALTER TABLE problems ADD CONSTRAINT fk_problems_practice_version FOREIGN KEY(practice_version_id) REFERENCES problem_versions (version_id);
CREATE FUNCTION a_frozen_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.published_at IS NOT NULL THEN
    RAISE EXCEPTION 'published version is immutable' USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER frozen_version BEFORE UPDATE OR DELETE ON problem_versions
FOR EACH ROW EXECUTE FUNCTION a_frozen_version();
CREATE FUNCTION a_frozen_material() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE frozen timestamptz;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    SELECT published_at INTO frozen FROM problem_versions WHERE version_id=OLD.version_id FOR UPDATE;
    IF frozen IS NOT NULL THEN RAISE EXCEPTION 'published material is immutable' USING ERRCODE='23514'; END IF;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT published_at INTO frozen FROM problem_versions WHERE version_id=NEW.version_id FOR UPDATE;
    IF frozen IS NOT NULL THEN RAISE EXCEPTION 'published material is immutable' USING ERRCODE='23514'; END IF;
    RETURN NEW;
  END IF;
  RETURN OLD;
END;
$$;
CREATE TRIGGER frozen_testcase BEFORE INSERT OR UPDATE OR DELETE ON testcases
FOR EACH ROW EXECUTE FUNCTION a_frozen_material();
CREATE TRIGGER frozen_reference BEFORE INSERT OR UPDATE OR DELETE ON reference_programs
FOR EACH ROW EXECUTE FUNCTION a_frozen_material();
