
CREATE TABLE policy_guard (
	guard_id SERIAL NOT NULL,
	revision INTEGER NOT NULL,
	CONSTRAINT pk_policy_guard PRIMARY KEY (guard_id),
	CONSTRAINT ck_policy_guard_singleton CHECK (guard_id=1),
	CONSTRAINT ck_policy_guard_revision CHECK (revision>0)
)

;

CREATE TABLE audit_events (
	event_id UUID NOT NULL,
	actor_id UUID,
	actor_kind VARCHAR(10) NOT NULL,
	action VARCHAR(80) NOT NULL,
	object_type VARCHAR(40) NOT NULL,
	object_id UUID NOT NULL,
	before_after_digest VARCHAR(64) NOT NULL,
	reason TEXT NOT NULL,
	timestamp TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	request_id UUID NOT NULL,
	CONSTRAINT pk_audit_events PRIMARY KEY (event_id),
	CONSTRAINT fk_audit_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (user_id),
	CONSTRAINT ck_audit_events_actor_kind CHECK (actor_kind IN ('USER','SYSTEM')),
	CONSTRAINT ck_audit_events_actor_required CHECK ((actor_kind='USER' AND actor_id IS NOT NULL) OR (actor_kind='SYSTEM' AND actor_id IS NULL))
)

;
CREATE INDEX ix_audit_actor ON audit_events (actor_id, timestamp);
CREATE INDEX ix_audit_object ON audit_events (object_type, object_id);
CREATE INDEX ix_audit_time ON audit_events (timestamp);

CREATE TABLE outbox_events (
	event_id UUID NOT NULL,
	event_key VARCHAR(100) NOT NULL,
	event_type VARCHAR(80) NOT NULL,
	payload JSONB NOT NULL,
	state VARCHAR(10) NOT NULL,
	tries BIGINT NOT NULL,
	next_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_outbox_events PRIMARY KEY (event_id),
	CONSTRAINT uq_outbox_events_event_key UNIQUE (event_key),
	CONSTRAINT ck_outbox_events_state CHECK (state IN ('READY','SENDING','SENT','FAILED')),
	CONSTRAINT ck_outbox_events_tries CHECK (tries>=0)
)

;
CREATE INDEX ix_outbox_ready ON outbox_events (state, next_at);
INSERT INTO policy_guard VALUES(1,1);
CREATE FUNCTION deny_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit is append only' USING ERRCODE='23514'; END $$;
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation();
