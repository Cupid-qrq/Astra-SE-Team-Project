CREATE TABLE capacity_control (
	control_id SERIAL NOT NULL,
	pending_count INTEGER NOT NULL,
	CONSTRAINT pk_capacity_control PRIMARY KEY (control_id),
	CONSTRAINT ck_capacity_control_singleton CHECK (control_id=1),
	CONSTRAINT ck_capacity_control_pending CHECK (pending_count BETWEEN 0 AND 100)
)

;


CREATE TABLE admission_users (
	user_id UUID NOT NULL,
	last_accepted_at TIMESTAMP(3) WITH TIME ZONE,
	pending_count INTEGER NOT NULL,
	CONSTRAINT pk_admission_users PRIMARY KEY (user_id),
	CONSTRAINT ck_admission_users_pending CHECK (pending_count BETWEEN 0 AND 3),
	CONSTRAINT fk_admission_users_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id)
)

;


CREATE TABLE submissions (
	submission_id UUID NOT NULL,
	user_id UUID NOT NULL,
	assignment_id UUID NOT NULL,
	problem_id UUID NOT NULL,
	version_id UUID NOT NULL,
	language_key VARCHAR(10) NOT NULL,
	code BYTEA NOT NULL,
	code_sha256 VARCHAR(64) NOT NULL,
	intent VARCHAR(8) NOT NULL,
	mode VARCHAR(8) NOT NULL,
	accepted_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	idempotency_key UUID NOT NULL,
	request_digest VARCHAR(64) NOT NULL,
	original_receipt JSONB NOT NULL,
	active_basis_id UUID,
	revision INTEGER NOT NULL,
	CONSTRAINT pk_submissions PRIMARY KEY (submission_id),
	CONSTRAINT fk_submissions_assignment_id_assignment_items FOREIGN KEY(assignment_id, problem_id) REFERENCES assignment_items (assignment_id, problem_id),
	CONSTRAINT uq_submissions_idempotency UNIQUE (user_id, idempotency_key),
	CONSTRAINT ck_submissions_language CHECK (language_key IN ('cpp17','python3')),
	CONSTRAINT ck_submissions_intent CHECK (intent IN ('FORMAL','PRACTICE') AND mode=intent),
	CONSTRAINT ck_submissions_code_size CHECK (octet_length(code) BETWEEN 1 AND 65536),
	CONSTRAINT ck_submissions_digest CHECK (code_sha256 ~ '^[0-9a-f]{64}$' AND request_digest ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_submissions_revision CHECK (revision>0),
	CONSTRAINT fk_submissions_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id),
	CONSTRAINT fk_submissions_version_id_problem_versions FOREIGN KEY(version_id) REFERENCES problem_versions (version_id)
)

;


CREATE TABLE result_bases (
	basis_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	batch_id UUID,
	target_version_id UUID NOT NULL,
	current_attempt_id UUID,
	current_cycle_id UUID,
	processing_state VARCHAR(12) NOT NULL,
	CONSTRAINT pk_result_bases PRIMARY KEY (basis_id),
	CONSTRAINT uq_basis_owner UNIQUE (submission_id, basis_id),
	CONSTRAINT uq_basis_batch UNIQUE (batch_id, submission_id),
	CONSTRAINT ck_result_bases_state CHECK (processing_state IN ('QUEUED','RUNNING','RETRY_WAIT','FINISHED')),
	CONSTRAINT fk_result_bases_submission_id_submissions FOREIGN KEY(submission_id) REFERENCES submissions (submission_id),
	CONSTRAINT fk_result_bases_target_version_id_problem_versions FOREIGN KEY(target_version_id) REFERENCES problem_versions (version_id)
)

;


CREATE TABLE processing_cycles (
	cycle_id UUID NOT NULL,
	basis_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	started_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	finished_at TIMESTAMP(3) WITH TIME ZONE,
	auto_retry_count INTEGER NOT NULL,
	capacity_held BOOLEAN NOT NULL,
	trigger VARCHAR(8) NOT NULL,
	reason VARCHAR(500),
	CONSTRAINT pk_processing_cycles PRIMARY KEY (cycle_id),
	CONSTRAINT fk_processing_cycles_submission_id_result_bases FOREIGN KEY(submission_id, basis_id) REFERENCES result_bases (submission_id, basis_id),
	CONSTRAINT uq_cycle_owner UNIQUE (submission_id, basis_id, cycle_id),
	CONSTRAINT ck_processing_cycles_retry CHECK (auto_retry_count IN (0,1)),
	CONSTRAINT ck_processing_cycles_trigger CHECK (trigger IN ('INITIAL','REJUDGE','MANUAL')),
	CONSTRAINT ck_processing_cycles_capacity CHECK (capacity_held=(finished_at IS NULL))
)

;


CREATE TABLE attempts (
	attempt_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	basis_id UUID NOT NULL,
	cycle_id UUID NOT NULL,
	generation INTEGER NOT NULL,
	state VARCHAR(12) NOT NULL,
	verdict VARCHAR(3),
	reason_code VARCHAR(60),
	started_at TIMESTAMP(3) WITH TIME ZONE,
	finished_at TIMESTAMP(3) WITH TIME ZONE,
	time_ms BIGINT,
	memory_bytes BIGINT,
	engine_meta JSONB NOT NULL,
	feedback_version_id UUID,
	CONSTRAINT pk_attempts PRIMARY KEY (attempt_id),
	CONSTRAINT fk_attempts_submission_id_processing_cycles FOREIGN KEY(submission_id, basis_id, cycle_id) REFERENCES processing_cycles (submission_id, basis_id, cycle_id),
	CONSTRAINT uq_attempt_generation UNIQUE (submission_id, generation),
	CONSTRAINT uq_attempt_owner UNIQUE (submission_id, basis_id, attempt_id),
	CONSTRAINT ck_attempts_generation CHECK (generation>0),
	CONSTRAINT ck_attempts_state CHECK (state IN ('QUEUED','RUNNING','RETRY_WAIT','FINISHED')),
	CONSTRAINT ck_attempts_finished CHECK ((state='FINISHED')=(verdict IS NOT NULL) AND (state='FINISHED')=(finished_at IS NOT NULL)),
	CONSTRAINT ck_attempts_verdict CHECK (verdict IN ('AC','WA','CE','TLE','RE','SE')),
	CONSTRAINT ck_attempts_metrics CHECK (time_ms>=0 AND memory_bytes>=0),
	CONSTRAINT fk_attempts_feedback_version_id_feedback_versions FOREIGN KEY(feedback_version_id) REFERENCES feedback_versions (version_id)
)

;


CREATE TABLE case_results (
	attempt_id UUID NOT NULL,
	"order" INTEGER NOT NULL,
	testcase_id UUID NOT NULL,
	verdict VARCHAR(7) NOT NULL,
	cpu_ms BIGINT,
	memory_bytes BIGINT,
	engine_meta JSONB NOT NULL,
	CONSTRAINT pk_case_results PRIMARY KEY (attempt_id, "order"),
	CONSTRAINT ck_case_results_order CHECK ("order" BETWEEN 1 AND 10),
	CONSTRAINT ck_case_results_verdict CHECK (verdict IN ('AC','WA','CE','TLE','RE','SE','SKIPPED')),
	CONSTRAINT ck_case_results_metrics CHECK (cpu_ms>=0 AND memory_bytes>=0),
	CONSTRAINT fk_case_results_attempt_id_attempts FOREIGN KEY(attempt_id) REFERENCES attempts (attempt_id),
	CONSTRAINT fk_case_results_testcase_id_testcases FOREIGN KEY(testcase_id) REFERENCES testcases (testcase_id)
)

;


CREATE TABLE queue_jobs (
	job_id UUID NOT NULL,
	attempt_id UUID NOT NULL,
	kind VARCHAR(8) NOT NULL,
	state VARCHAR(8) NOT NULL,
	ready_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	lease_until TIMESTAMP(3) WITH TIME ZONE,
	deadline TIMESTAMP(3) WITH TIME ZONE,
	lease_epoch BIGINT NOT NULL,
	worker_id UUID,
	current_execution VARCHAR(64),
	CONSTRAINT pk_queue_jobs PRIMARY KEY (job_id),
	CONSTRAINT ck_queue_jobs_kind CHECK (kind IN ('NORMAL','REJUDGE')),
	CONSTRAINT ck_queue_jobs_state CHECK (state IN ('READY','LEASED','DONE')),
	CONSTRAINT ck_queue_jobs_epoch CHECK (lease_epoch>=0),
	CONSTRAINT ck_queue_jobs_execution CHECK (current_execution IS NULL OR current_execution ~ '^[0-9a-f]{64}$'),
	CONSTRAINT uq_queue_jobs_attempt_id UNIQUE (attempt_id),
	CONSTRAINT fk_queue_jobs_attempt_id_attempts FOREIGN KEY(attempt_id) REFERENCES attempts (attempt_id)
)

;

ALTER TABLE submissions ADD CONSTRAINT fk_submission_active_basis FOREIGN KEY(submission_id, active_basis_id) REFERENCES result_bases (submission_id, basis_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE result_bases ADD CONSTRAINT fk_basis_current_cycle FOREIGN KEY(submission_id, basis_id, current_cycle_id) REFERENCES processing_cycles (submission_id, basis_id, cycle_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE result_bases ADD CONSTRAINT fk_basis_current_attempt FOREIGN KEY(submission_id, basis_id, current_attempt_id) REFERENCES attempts (submission_id, basis_id, attempt_id) DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX ix_submissions_history ON submissions (assignment_id, user_id, accepted_at, submission_id);

CREATE UNIQUE INDEX uq_original_basis ON result_bases (submission_id) WHERE batch_id IS NULL;

CREATE UNIQUE INDEX uq_cycle_capacity ON processing_cycles (submission_id) WHERE capacity_held;

CREATE INDEX ix_queue_ready ON queue_jobs (kind, state, ready_at, created_at, job_id);

INSERT INTO capacity_control(control_id,pending_count) VALUES(1,0);

CREATE FUNCTION protect_submission_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(NEW.user_id,NEW.assignment_id,NEW.problem_id,NEW.version_id,NEW.language_key,
        NEW.code,NEW.code_sha256,NEW.intent,NEW.mode,NEW.accepted_at,NEW.idempotency_key,
        NEW.request_digest,NEW.original_receipt)
 IS DISTINCT FROM ROW(OLD.user_id,OLD.assignment_id,OLD.problem_id,OLD.version_id,OLD.language_key,
        OLD.code,OLD.code_sha256,OLD.intent,OLD.mode,OLD.accepted_at,OLD.idempotency_key,
        OLD.request_digest,OLD.original_receipt) THEN
  RAISE EXCEPTION 'submission identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER submission_identity_immutable BEFORE UPDATE ON submissions
FOR EACH ROW EXECUTE FUNCTION protect_submission_identity();
