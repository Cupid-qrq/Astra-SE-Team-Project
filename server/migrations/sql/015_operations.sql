CREATE TABLE fairness_incidents (
	incident_id UUID NOT NULL,
	started_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	recovered_at TIMESTAMP(3) WITH TIME ZONE,
	reason_code VARCHAR(60) NOT NULL,
	rejected_count INTEGER NOT NULL,
	evidence_refs JSONB NOT NULL,
	evidence_incomplete BOOLEAN NOT NULL,
	detected_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	displayed_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	persisted_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	recovery_started_at TIMESTAMP(3) WITH TIME ZONE,
	revision INTEGER NOT NULL,
	CONSTRAINT pk_fairness_incidents PRIMARY KEY (incident_id),
	CONSTRAINT ck_fairness_incidents_interval CHECK (recovered_at IS NULL OR recovered_at>=started_at)
)

;


CREATE TABLE notifications (
	notification_id UUID NOT NULL,
	user_id UUID NOT NULL,
	event_key VARCHAR(140) NOT NULL,
	title VARCHAR(100) NOT NULL,
	body TEXT NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	read_at TIMESTAMP(3) WITH TIME ZONE,
	CONSTRAINT pk_notifications PRIMARY KEY (notification_id),
	CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id),
	CONSTRAINT uq_notifications_event_key UNIQUE (event_key)
)

;


CREATE TABLE course_cleanup (
	course_id UUID NOT NULL,
	cleaned_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	purge_due_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	purged_at TIMESTAMP(3) WITH TIME ZONE,
	confirmed_by UUID NOT NULL,
	CONSTRAINT pk_course_cleanup PRIMARY KEY (course_id),
	CONSTRAINT fk_course_cleanup_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id),
	CONSTRAINT fk_course_cleanup_confirmed_by_users FOREIGN KEY(confirmed_by) REFERENCES users (user_id)
)

;


CREATE TABLE course_holds (
	hold_id UUID NOT NULL,
	course_id UUID NOT NULL,
	reason VARCHAR(500) NOT NULL,
	created_by UUID NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	released_at TIMESTAMP(3) WITH TIME ZONE,
	CONSTRAINT pk_course_holds PRIMARY KEY (hold_id),
	CONSTRAINT fk_course_holds_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id),
	CONSTRAINT fk_course_holds_created_by_users FOREIGN KEY(created_by) REFERENCES users (user_id)
)

;


CREATE TABLE incident_assignments (
	incident_id UUID NOT NULL,
	assignment_id UUID NOT NULL,
	decision VARCHAR(12) NOT NULL,
	old_due TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	new_due TIMESTAMP(3) WITH TIME ZONE,
	approved_by UUID,
	approved_at TIMESTAMP(3) WITH TIME ZONE,
	overlap_ms INTEGER,
	reason VARCHAR(500),
	CONSTRAINT pk_incident_assignments PRIMARY KEY (incident_id, assignment_id),
	CONSTRAINT ck_incident_assignments_decision CHECK (decision IN ('PENDING','EXTEND','NO_IMPACT')),
	CONSTRAINT fk_incident_assignments_incident_id_fairness_incidents FOREIGN KEY(incident_id) REFERENCES fairness_incidents (incident_id),
	CONSTRAINT fk_incident_assignments_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (assignment_id),
	CONSTRAINT fk_incident_assignments_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (user_id)
)

;


CREATE TABLE incident_requests (
	incident_id UUID NOT NULL,
	request_id UUID NOT NULL,
	assignment_id UUID,
	reason_code VARCHAR(60) NOT NULL,
	observed_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_incident_requests PRIMARY KEY (incident_id, request_id),
	CONSTRAINT fk_incident_requests_incident_id_fairness_incidents FOREIGN KEY(incident_id) REFERENCES fairness_incidents (incident_id),
	CONSTRAINT fk_incident_requests_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (assignment_id)
)

;
