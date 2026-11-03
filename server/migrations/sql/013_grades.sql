CREATE TABLE grade_versions (
	grade_version UUID NOT NULL,
	assignment_id UUID NOT NULL,
	assignment_revision INTEGER NOT NULL,
	grade_epoch INTEGER NOT NULL,
	state VARCHAR(12) NOT NULL,
	published_at TIMESTAMP(3) WITH TIME ZONE,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_grade_versions PRIMARY KEY (grade_version),
	CONSTRAINT ck_grade_versions_state CHECK (state IN ('PROVISIONAL','PUBLISHED')),
	CONSTRAINT fk_grade_versions_assignment_id_assignments FOREIGN KEY(assignment_id) REFERENCES assignments (assignment_id)
)

;


CREATE TABLE grade_students (
	grade_version UUID NOT NULL,
	student_id UUID NOT NULL,
	total INTEGER NOT NULL,
	state VARCHAR(8) NOT NULL,
	CONSTRAINT pk_grade_students PRIMARY KEY (grade_version, student_id),
	CONSTRAINT ck_grade_students_total CHECK (total BETWEEN 0 AND 100),
	CONSTRAINT ck_grade_students_state CHECK (state IN ('READY','PENDING')),
	CONSTRAINT fk_grade_students_grade_version_grade_versions FOREIGN KEY(grade_version) REFERENCES grade_versions (grade_version),
	CONSTRAINT fk_grade_students_student_id_users FOREIGN KEY(student_id) REFERENCES users (user_id)
)

;


CREATE TABLE grade_items (
	grade_version UUID NOT NULL,
	student_id UUID NOT NULL,
	problem_id UUID NOT NULL,
	points INTEGER NOT NULL,
	score INTEGER NOT NULL,
	source_attempt_id UUID,
	target_version_id UUID NOT NULL,
	CONSTRAINT pk_grade_items PRIMARY KEY (grade_version, student_id, problem_id),
	CONSTRAINT fk_grade_items_grade_version_grade_students FOREIGN KEY(grade_version, student_id) REFERENCES grade_students (grade_version, student_id),
	CONSTRAINT ck_grade_items_score CHECK (points BETWEEN 1 AND 100 AND score IN (0,points)),
	CONSTRAINT fk_grade_items_problem_id_problems FOREIGN KEY(problem_id) REFERENCES problems (problem_id),
	CONSTRAINT fk_grade_items_source_attempt_id_attempts FOREIGN KEY(source_attempt_id) REFERENCES attempts (attempt_id),
	CONSTRAINT fk_grade_items_target_version_id_problem_versions FOREIGN KEY(target_version_id) REFERENCES problem_versions (version_id)
)

;

CREATE FUNCTION protect_grade_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'grade snapshots are immutable' USING ERRCODE='23514';
END $$;
CREATE TRIGGER grade_version_immutable BEFORE UPDATE ON grade_versions FOR EACH ROW EXECUTE FUNCTION protect_grade_snapshot();
CREATE TRIGGER grade_student_immutable BEFORE UPDATE ON grade_students FOR EACH ROW EXECUTE FUNCTION protect_grade_snapshot();
CREATE TRIGGER grade_item_immutable BEFORE UPDATE ON grade_items FOR EACH ROW EXECUTE FUNCTION protect_grade_snapshot();
