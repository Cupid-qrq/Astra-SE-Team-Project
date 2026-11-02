CREATE TABLE model_configs (
	config_id UUID NOT NULL,
	provider VARCHAR(80) NOT NULL,
	model_id VARCHAR(120) NOT NULL,
	version_label VARCHAR(120) NOT NULL,
	terms_review_ref VARCHAR(500) NOT NULL,
	price_verified_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	input_price NUMERIC NOT NULL,
	output_price NUMERIC NOT NULL,
	max_input_tokens INTEGER NOT NULL,
	max_output_tokens INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	CONSTRAINT pk_model_configs PRIMARY KEY (config_id),
	CONSTRAINT ck_model_configs_model_limits CHECK (input_price >= 0 AND output_price >= 0 AND input_price + output_price > 0 AND max_input_tokens > 0 AND max_output_tokens > 0)
);

CREATE TABLE ai_hints (
	hint_id UUID NOT NULL,
	user_id UUID NOT NULL,
	course_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	request_key UUID NOT NULL,
	request_digest VARCHAR(64) NOT NULL,
	question VARCHAR(500) NOT NULL,
	accepted_date DATE NOT NULL,
	status VARCHAR(8) NOT NULL,
	reason_code VARCHAR(80),
	template_version_id UUID NOT NULL,
	model_config_id UUID NOT NULL,
	feedback_version_id UUID NOT NULL,
	accepted_policy_digest VARCHAR(64) NOT NULL,
	dispatch_policy_digest VARCHAR(64),
	authorized_at TIMESTAMP(3) WITH TIME ZONE,
	consented_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	sections JSONB,
	usage JSONB,
	provider_request_id VARCHAR(128),
	CONSTRAINT pk_ai_hints PRIMARY KEY (hint_id),
	CONSTRAINT uq_ai_hints_user_id UNIQUE (user_id, request_key),
	CONSTRAINT ck_ai_hints_hint_status CHECK (status IN ('PENDING','READY','FAILED','BLOCKED') AND ((status = 'READY') = (sections IS NOT NULL))),
	CONSTRAINT fk_ai_hints_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id),
	CONSTRAINT fk_ai_hints_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id),
	CONSTRAINT fk_ai_hints_template_version_id_template_versions FOREIGN KEY(template_version_id) REFERENCES template_versions (version_id),
	CONSTRAINT fk_ai_hints_model_config_id_model_configs FOREIGN KEY(model_config_id) REFERENCES model_configs (config_id),
	CONSTRAINT fk_ai_hints_feedback_version_id_feedback_versions FOREIGN KEY(feedback_version_id) REFERENCES feedback_versions (version_id)
);

CREATE UNIQUE INDEX uq_personal_pending_hint ON ai_hints (user_id) WHERE status = 'PENDING';

CREATE INDEX ix_ai_hints_user_history ON ai_hints(user_id, created_at, hint_id);

CREATE TABLE hint_jobs (
	hint_id UUID NOT NULL,
	state VARCHAR(8) NOT NULL,
	queued_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	started_at TIMESTAMP(3) WITH TIME ZONE,
	deadline_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	lease_epoch INTEGER NOT NULL,
	CONSTRAINT pk_hint_jobs PRIMARY KEY (hint_id),
	CONSTRAINT ck_hint_jobs_job_state CHECK (state IN ('WAITING','RUNNING','DONE') AND lease_epoch >= 0),
	CONSTRAINT fk_hint_jobs_hint_id_ai_hints FOREIGN KEY(hint_id) REFERENCES ai_hints (hint_id)
);

CREATE INDEX ix_hint_jobs_queue ON hint_jobs (state, queued_at, hint_id);

CREATE TABLE hint_feedback (
	hint_id UUID NOT NULL,
	user_id UUID NOT NULL,
	rating VARCHAR(12) NOT NULL,
	comment VARCHAR(500) NOT NULL,
	updated_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_hint_feedback PRIMARY KEY (hint_id),
	CONSTRAINT ck_hint_feedback_hint_rating CHECK (rating IN ('USEFUL','NOT_USEFUL','ERROR')),
	CONSTRAINT fk_hint_feedback_hint_id_ai_hints FOREIGN KEY(hint_id) REFERENCES ai_hints (hint_id),
	CONSTRAINT fk_hint_feedback_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id)
);

CREATE TABLE quota_ledger (
	user_id UUID NOT NULL,
	accepted_date DATE NOT NULL,
	ready INTEGER NOT NULL,
	reserved INTEGER NOT NULL,
	CONSTRAINT pk_quota_ledger PRIMARY KEY (user_id, accepted_date),
	CONSTRAINT ck_quota_ledger_personal_quota CHECK (ready >= 0 AND reserved >= 0 AND ready + reserved <= 20),
	CONSTRAINT fk_quota_ledger_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id)
);

CREATE TABLE budget_accounts (
	scope_key VARCHAR(20) NOT NULL,
	limit_amount NUMERIC NOT NULL,
	settled_amount NUMERIC NOT NULL,
	reserved_amount NUMERIC NOT NULL,
	uncertain_amount NUMERIC NOT NULL,
	revision INTEGER NOT NULL,
	CONSTRAINT pk_budget_accounts PRIMARY KEY (scope_key),
	CONSTRAINT ck_budget_accounts_budget_amounts CHECK (limit_amount > 0 AND settled_amount >= 0 AND reserved_amount >= 0 AND uncertain_amount >= 0 AND revision > 0)
);

CREATE TABLE budget_reservations (
	hint_id UUID NOT NULL,
	accepted_date DATE NOT NULL,
	cost_upper NUMERIC NOT NULL,
	actual NUMERIC,
	state VARCHAR(10) NOT NULL,
	CONSTRAINT pk_budget_reservations PRIMARY KEY (hint_id),
	CONSTRAINT ck_budget_reservations_reservation_state CHECK (cost_upper > 0 AND state IN ('RESERVED','RELEASED','UNCERTAIN','SETTLED') AND ((state='SETTLED')=(actual IS NOT NULL)) AND (actual IS NULL OR actual>=0)),
	CONSTRAINT fk_budget_reservations_hint_id_ai_hints FOREIGN KEY(hint_id) REFERENCES ai_hints (hint_id)
);

CREATE FUNCTION reject_model_config_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable model configuration'; END $$;
CREATE TRIGGER immutable_model_config BEFORE UPDATE OR DELETE ON model_configs FOR EACH ROW EXECUTE FUNCTION reject_model_config_change();
