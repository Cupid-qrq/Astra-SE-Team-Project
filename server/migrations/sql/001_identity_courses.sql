
CREATE TABLE login_attempts (
	attempt_id UUID NOT NULL,
	login_digest VARCHAR(64) NOT NULL,
	source_digest VARCHAR(64) NOT NULL,
	succeeded BOOLEAN NOT NULL,
	attempted_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_login_attempts PRIMARY KEY (attempt_id)
)

;
CREATE INDEX ix_login_attempts_login_time ON login_attempts (login_digest, attempted_at);
CREATE INDEX ix_login_attempts_source_time ON login_attempts (source_digest, attempted_at);

CREATE TABLE users (
	user_id UUID NOT NULL,
	login_name VARCHAR(32) NOT NULL,
	display_name VARCHAR(40) NOT NULL,
	role VARCHAR(10) NOT NULL,
	status VARCHAR(10) NOT NULL,
	password_hash VARCHAR(256) NOT NULL,
	must_change_password BOOLEAN NOT NULL,
	revision INTEGER NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_users PRIMARY KEY (user_id),
	CONSTRAINT ck_users_role CHECK (role IN ('STUDENT','TEACHER','ADMIN')),
	CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE','DISABLED')),
	CONSTRAINT ck_users_login CHECK (login_name ~ '^[A-Za-z0-9_]{3,32}$'),
	CONSTRAINT ck_users_display CHECK (char_length(display_name) BETWEEN 1 AND 40),
	CONSTRAINT ck_users_revision CHECK (revision > 0),
	CONSTRAINT uq_users_login_name UNIQUE (login_name)
)

;

CREATE TABLE courses (
	course_id UUID NOT NULL,
	teacher_id UUID NOT NULL,
	title VARCHAR(100) NOT NULL,
	status VARCHAR(10) NOT NULL,
	revision INTEGER NOT NULL,
	archived_at TIMESTAMP(3) WITH TIME ZONE,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_courses PRIMARY KEY (course_id),
	CONSTRAINT ck_courses_revision CHECK (revision > 0),
	CONSTRAINT ck_courses_title CHECK (char_length(title) BETWEEN 1 AND 100),
	CONSTRAINT ck_courses_archive CHECK ((status='ARCHIVED') = (archived_at IS NOT NULL)),
	CONSTRAINT ck_courses_status CHECK (status IN ('ACTIVE','ARCHIVED')),
	CONSTRAINT fk_courses_teacher_id_users FOREIGN KEY(teacher_id) REFERENCES users (user_id)
)

;
CREATE INDEX ix_courses_teacher_status ON courses (teacher_id, status);

CREATE TABLE sessions (
	session_id UUID NOT NULL,
	user_id UUID,
	token_hash VARCHAR(64) NOT NULL,
	csrf_hash VARCHAR(64) NOT NULL,
	created_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	last_seen_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP(3) WITH TIME ZONE,
	CONSTRAINT pk_sessions PRIMARY KEY (session_id),
	CONSTRAINT fk_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id),
	CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash)
)

;
CREATE INDEX ix_sessions_user_expiry ON sessions (user_id, expires_at);

CREATE TABLE course_members (
	course_id UUID NOT NULL,
	user_id UUID NOT NULL,
	status VARCHAR(10) NOT NULL,
	joined_at TIMESTAMP(3) WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_course_members PRIMARY KEY (course_id, user_id),
	CONSTRAINT ck_course_members_status CHECK (status IN ('ACTIVE','DISABLED')),
	CONSTRAINT fk_course_members_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id),
	CONSTRAINT fk_course_members_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id)
)

;
CREATE INDEX ix_members_user_course ON course_members (user_id, course_id);
