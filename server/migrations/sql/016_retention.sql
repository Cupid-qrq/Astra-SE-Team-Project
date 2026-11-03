CREATE TABLE emergency_grants (
	grant_id UUID NOT NULL,
	admin_id UUID NOT NULL,
	incident_id UUID NOT NULL,
	scope JSONB NOT NULL,
	expires_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP(3) WITH TIME ZONE,
	reason VARCHAR(500) NOT NULL,
	CONSTRAINT pk_emergency_grants PRIMARY KEY (grant_id),
	CONSTRAINT fk_emergency_grants_admin_id_users FOREIGN KEY(admin_id) REFERENCES users (user_id),
	CONSTRAINT fk_emergency_grants_incident_id_fairness_incidents FOREIGN KEY(incident_id) REFERENCES fairness_incidents (incident_id)
)

;


CREATE TABLE runtime_config_versions (
	config_version UUID NOT NULL,
	payload JSONB NOT NULL,
	checksum VARCHAR(64) NOT NULL,
	created_by UUID NOT NULL,
	reason VARCHAR(500) NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	revision INTEGER NOT NULL,
	CONSTRAINT pk_runtime_config_versions PRIMARY KEY (config_version),
	CONSTRAINT fk_runtime_config_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (user_id),
	CONSTRAINT uq_runtime_config_versions_revision UNIQUE (revision)
)

;


CREATE TABLE retention_plans (
	plan_id UUID NOT NULL,
	course_id UUID NOT NULL,
	object_digest VARCHAR(64) NOT NULL,
	state VARCHAR(12) NOT NULL,
	revision INTEGER NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_retention_plans PRIMARY KEY (plan_id),
	CONSTRAINT fk_retention_plans_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id)
)

;


CREATE TABLE retention_confirmations (
	confirmation_id UUID NOT NULL,
	plan_id UUID NOT NULL,
	teacher_id UUID NOT NULL,
	object_digest VARCHAR(64) NOT NULL,
	reason VARCHAR(500) NOT NULL,
	confirmed_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_retention_confirmations PRIMARY KEY (confirmation_id),
	CONSTRAINT fk_retention_confirmations_plan_id_retention_plans FOREIGN KEY(plan_id) REFERENCES retention_plans (plan_id),
	CONSTRAINT fk_retention_confirmations_teacher_id_users FOREIGN KEY(teacher_id) REFERENCES users (user_id)
)

;
