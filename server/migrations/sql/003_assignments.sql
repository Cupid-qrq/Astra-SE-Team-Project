
CREATE TABLE assignments (
	assignment_id UUID NOT NULL,
	course_id UUID NOT NULL,
	title VARCHAR(100) NOT NULL,
	open_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	due_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	ai_policy VARCHAR(10) NOT NULL,
	published_at TIMESTAMP(3) WITH TIME ZONE,
	revision INTEGER NOT NULL,
	grade_epoch BIGINT NOT NULL,
	fairness_review VARCHAR(10) NOT NULL,
	active_grade_version UUID,
	active_rejudge_batch_id UUID,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_assignments PRIMARY KEY (assignment_id),
	CONSTRAINT ck_assignments_time_range CHECK (open_at < due_at),
	CONSTRAINT ck_assignments_revisions CHECK (revision > 0 AND grade_epoch > 0),
	CONSTRAINT ck_assignments_ai_policy CHECK (ai_policy IN ('DISABLED','GUIDED')),
	CONSTRAINT ck_assignments_fairness CHECK (fairness_review IN ('NONE','PENDING','RESOLVED')),
	CONSTRAINT ck_assignments_title CHECK (char_length(title) BETWEEN 1 AND 100),
	CONSTRAINT fk_assignments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id)
)

;
CREATE INDEX ix_assignments_course_due ON assignments (course_id, due_at);

CREATE TABLE assignment_items (
	assignment_id UUID NOT NULL,
	problem_id UUID NOT NULL,
	original_version_id UUID NOT NULL,
	effective_version_id UUID NOT NULL,
	points INTEGER NOT NULL,
	CONSTRAINT pk_assignment_items PRIMARY KEY (assignment_id, problem_id),
	CONSTRAINT ck_assignment_items_points CHECK (points BETWEEN 1 AND 100),
	CONSTRAINT fk_items_original_version FOREIGN KEY(problem_id, original_version_id) REFERENCES problem_versions (problem_id, version_id),
	CONSTRAINT fk_items_effective_version FOREIGN KEY(problem_id, effective_version_id) REFERENCES problem_versions (problem_id, version_id),
	CONSTRAINT fk_assignment_items_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (assignment_id),
	CONSTRAINT fk_assignment_items_problem_id_problems FOREIGN KEY(problem_id) REFERENCES problems (problem_id)
)

;
CREATE INDEX ix_items_effective_version ON assignment_items (effective_version_id);
CREATE INDEX ix_items_original_version ON assignment_items (original_version_id);
CREATE FUNCTION a_assignment_content_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.published_at IS NOT NULL AND
     (NEW.title IS DISTINCT FROM OLD.title OR NEW.course_id IS DISTINCT FROM OLD.course_id OR
      NEW.open_at IS DISTINCT FROM OLD.open_at OR NEW.published_at IS DISTINCT FROM OLD.published_at) THEN
    RAISE EXCEPTION 'published assignment content is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER assignment_content_guard BEFORE UPDATE ON assignments
FOR EACH ROW EXECUTE FUNCTION a_assignment_content_guard();
CREATE FUNCTION a_assignment_item_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE frozen timestamptz;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    SELECT published_at INTO frozen FROM assignments WHERE assignment_id=OLD.assignment_id FOR UPDATE;
    IF frozen IS NOT NULL THEN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'published item cannot be deleted' USING ERRCODE='23514'; END IF;
      IF NEW.assignment_id IS DISTINCT FROM OLD.assignment_id OR NEW.problem_id IS DISTINCT FROM OLD.problem_id OR
         NEW.original_version_id IS DISTINCT FROM OLD.original_version_id OR NEW.points IS DISTINCT FROM OLD.points THEN
        RAISE EXCEPTION 'published item content is immutable' USING ERRCODE='23514';
      END IF;
    END IF;
  END IF;
  IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND NEW.assignment_id IS DISTINCT FROM OLD.assignment_id) THEN
    SELECT published_at INTO frozen FROM assignments WHERE assignment_id=NEW.assignment_id FOR UPDATE;
    IF frozen IS NOT NULL THEN RAISE EXCEPTION 'cannot add to published assignment' USING ERRCODE='23514'; END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER assignment_item_guard BEFORE INSERT OR UPDATE OR DELETE ON assignment_items
FOR EACH ROW EXECUTE FUNCTION a_assignment_item_guard();
