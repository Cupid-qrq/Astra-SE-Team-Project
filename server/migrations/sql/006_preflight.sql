CREATE TABLE preflight_runs (
 preflight_id uuid CONSTRAINT pk_preflight_runs PRIMARY KEY,
 version_id uuid NOT NULL CONSTRAINT fk_preflight_runs_version_id_problem_versions REFERENCES problem_versions(version_id),
 version_revision integer NOT NULL, content_digest varchar(64) NOT NULL, profile_hash varchar(64) NOT NULL,
 frozen_blob bytea NOT NULL, state varchar(10) NOT NULL,
 created_by uuid NOT NULL CONSTRAINT fk_preflight_runs_created_by_users REFERENCES users(user_id),
 created_at timestamptz(3) NOT NULL, started_at timestamptz(3), finished_at timestamptz(3),
 CONSTRAINT ck_preflight_runs_revision CHECK(version_revision>0),
 CONSTRAINT ck_preflight_runs_content_digest CHECK(content_digest ~ '^[0-9a-f]{64}$'),
 CONSTRAINT ck_preflight_runs_profile_hash CHECK(profile_hash ~ '^[0-9a-f]{64}$'),
 CONSTRAINT ck_preflight_runs_snapshot_size CHECK(octet_length(frozen_blob) BETWEEN 1 AND 16777216),
 CONSTRAINT ck_preflight_runs_state CHECK(state IN ('QUEUED','RUNNING','PASSED','FAILED')),
 CONSTRAINT ck_preflight_runs_finished CHECK((state IN ('PASSED','FAILED')) = (finished_at IS NOT NULL)),
 CONSTRAINT ck_preflight_runs_started CHECK((state='QUEUED' AND started_at IS NULL) OR (state<>'QUEUED' AND started_at IS NOT NULL))
);
CREATE INDEX ix_preflight_version ON preflight_runs(version_id);
CREATE INDEX ix_preflight_author ON preflight_runs(created_by);
CREATE UNIQUE INDEX uq_preflight_active ON preflight_runs(version_id,content_digest,profile_hash) WHERE state IN ('QUEUED','RUNNING');
CREATE TABLE preflight_cases (
 preflight_id uuid CONSTRAINT fk_preflight_cases_preflight_id_preflight_runs REFERENCES preflight_runs(preflight_id),
 language_key varchar(10) NOT NULL, case_kind varchar(6) NOT NULL, case_order integer NOT NULL,
 state varchar(10) NOT NULL, verdict varchar(3), engine_meta jsonb NOT NULL,
 CONSTRAINT pk_preflight_cases PRIMARY KEY(preflight_id,language_key,case_kind,case_order),
 CONSTRAINT ck_preflight_cases_language CHECK(language_key IN ('cpp17','python3')),
 CONSTRAINT ck_preflight_cases_kind CHECK(case_kind IN ('SAMPLE','HIDDEN')),
 CONSTRAINT ck_preflight_cases_case_order CHECK(case_order BETWEEN 1 AND CASE WHEN case_kind='SAMPLE' THEN 3 ELSE 10 END),
 CONSTRAINT ck_preflight_cases_state CHECK(state IN ('QUEUED','RUNNING','FINISHED','SKIPPED')),
 CONSTRAINT ck_preflight_cases_finished CHECK((state='FINISHED') = (verdict IS NOT NULL)),
 CONSTRAINT ck_preflight_cases_verdict CHECK(verdict IN ('AC','WA','CE','TLE','RE','SE'))
);
CREATE TABLE preflight_jobs (
 job_id uuid CONSTRAINT pk_preflight_jobs PRIMARY KEY,
 preflight_id uuid NOT NULL CONSTRAINT fk_preflight_jobs_preflight_id_preflight_runs REFERENCES preflight_runs(preflight_id),
 state varchar(10) NOT NULL, ready_at timestamptz(3) NOT NULL,
 CONSTRAINT uq_preflight_jobs_preflight_id UNIQUE(preflight_id),
 CONSTRAINT ck_preflight_jobs_state CHECK(state IN ('READY','DONE'))
);
CREATE INDEX ix_preflight_job_ready ON preflight_jobs(state,ready_at,job_id);
CREATE FUNCTION guard_preflight_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'preflight history is retained' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='preflight_runs' THEN
  IF (NEW.preflight_id,NEW.version_id,NEW.version_revision,NEW.content_digest,NEW.profile_hash,NEW.frozen_blob,NEW.created_by,NEW.created_at)
     IS DISTINCT FROM (OLD.preflight_id,OLD.version_id,OLD.version_revision,OLD.content_digest,OLD.profile_hash,OLD.frozen_blob,OLD.created_by,OLD.created_at)
     OR (OLD.state IN ('PASSED','FAILED') AND NEW IS DISTINCT FROM OLD)
  THEN RAISE EXCEPTION 'preflight binding or terminal history is immutable' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='preflight_cases' THEN
  IF (NEW.preflight_id,NEW.language_key,NEW.case_kind,NEW.case_order) IS DISTINCT FROM (OLD.preflight_id,OLD.language_key,OLD.case_kind,OLD.case_order)
     OR (OLD.state IN ('FINISHED','SKIPPED') AND NEW IS DISTINCT FROM OLD)
  THEN RAISE EXCEPTION 'preflight case binding or terminal history is immutable' USING ERRCODE='23514'; END IF;
 ELSE
  IF (NEW.job_id,NEW.preflight_id,NEW.ready_at) IS DISTINCT FROM (OLD.job_id,OLD.preflight_id,OLD.ready_at)
     OR (OLD.state='DONE' AND NEW IS DISTINCT FROM OLD)
  THEN RAISE EXCEPTION 'preflight job history is immutable' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER preflight_run_history BEFORE UPDATE OR DELETE ON preflight_runs FOR EACH ROW EXECUTE FUNCTION guard_preflight_history();
CREATE TRIGGER preflight_case_history BEFORE UPDATE OR DELETE ON preflight_cases FOR EACH ROW EXECUTE FUNCTION guard_preflight_history();
CREATE TRIGGER preflight_job_history BEFORE UPDATE OR DELETE ON preflight_jobs FOR EACH ROW EXECUTE FUNCTION guard_preflight_history();
