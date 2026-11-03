CREATE TABLE rejudge_batches (
	batch_id UUID NOT NULL,
	assignment_id UUID NOT NULL,
	problem_id UUID NOT NULL,
	new_version_id UUID NOT NULL,
	assignment_revision INTEGER NOT NULL,
	revision INTEGER NOT NULL,
	state VARCHAR(12) NOT NULL,
	reason VARCHAR(500) NOT NULL,
	range_checksum VARCHAR(64) NOT NULL,
	affected_count INTEGER NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_rejudge_batches PRIMARY KEY (batch_id),
	CONSTRAINT ck_rejudge_batches_state CHECK (state IN ('QUEUED','RUNNING','READY','FAILED','CANCELLED','ACTIVE')),
	CONSTRAINT fk_rejudge_batches_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (assignment_id),
	CONSTRAINT fk_rejudge_batches_problem_id_problems FOREIGN KEY(problem_id) REFERENCES problems (problem_id),
	CONSTRAINT fk_rejudge_batches_new_version_id_problem_versions FOREIGN KEY(new_version_id) REFERENCES problem_versions (version_id)
)

;


CREATE TABLE rejudge_members (
	batch_id UUID NOT NULL,
	submission_id UUID NOT NULL,
	basis_id UUID,
	state VARCHAR(8) NOT NULL,
	CONSTRAINT pk_rejudge_members PRIMARY KEY (batch_id, submission_id),
	CONSTRAINT ck_rejudge_members_state CHECK (state IN ('WAITING','RUNNING','FINISHED')),
	CONSTRAINT fk_rejudge_members_batch_id_rejudge_batches FOREIGN KEY(batch_id) REFERENCES rejudge_batches (batch_id),
	CONSTRAINT fk_rejudge_members_submission_id_submissions FOREIGN KEY(submission_id) REFERENCES submissions (submission_id),
	CONSTRAINT fk_rejudge_members_basis_id_result_bases FOREIGN KEY(basis_id) REFERENCES result_bases (basis_id)
)

;

CREATE UNIQUE INDEX uq_rejudge_open_assignment ON rejudge_batches (assignment_id) WHERE state IN ('QUEUED','RUNNING','READY','FAILED');

ALTER TABLE result_bases ADD CONSTRAINT fk_basis_rejudge_batch FOREIGN KEY(batch_id) REFERENCES rejudge_batches (batch_id);

ALTER TABLE scheduler_control ADD COLUMN cursor integer NOT NULL DEFAULT 0 CHECK(cursor BETWEEN 0 AND 4), ADD COLUMN previous_queue_mode varchar(12) NOT NULL DEFAULT 'EMPTY';
