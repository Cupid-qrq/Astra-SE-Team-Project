ALTER TABLE preflight_jobs ADD COLUMN lease_epoch bigint NOT NULL DEFAULT 0;
ALTER TABLE preflight_jobs ADD COLUMN lease_until timestamptz(3);
ALTER TABLE preflight_jobs ADD COLUMN deadline timestamptz(3);
ALTER TABLE preflight_jobs ADD COLUMN claimed_by uuid;
ALTER TABLE preflight_jobs ADD COLUMN current_execution varchar(64);
ALTER TABLE preflight_jobs ADD CONSTRAINT ck_preflight_jobs_epoch CHECK(lease_epoch>=0);
ALTER TABLE preflight_jobs ADD CONSTRAINT ck_preflight_jobs_execution CHECK(current_execution IS NULL OR current_execution ~ '^[0-9a-f]{64}$');
CREATE TABLE scheduler_control (control_id integer PRIMARY KEY, executor_binding varchar(64), CONSTRAINT ck_scheduler_control_singleton CHECK(control_id=1));
INSERT INTO scheduler_control(control_id) VALUES(1);
CREATE TABLE execution_slots (
 slot_id integer PRIMARY KEY,
 state varchar(16) NOT NULL,
 job_id uuid REFERENCES preflight_jobs(job_id),
 lease_epoch bigint NOT NULL DEFAULT 0,
 CONSTRAINT uq_execution_slots_job_id UNIQUE(job_id),
 CONSTRAINT ck_execution_slots_state CHECK(state IN ('FREE','BUSY','QUARANTINED')),
 CONSTRAINT ck_execution_slots_binding CHECK((state='FREE')=(job_id IS NULL)),
 CONSTRAINT ck_execution_slots_epoch CHECK(lease_epoch>=0)
);
INSERT INTO execution_slots(slot_id,state) VALUES(1,'FREE');
