-- Fail on invalid existing references; never manufacture or rewrite historical evidence.
ALTER TABLE preflight_runs ADD CONSTRAINT uq_preflight_version_run UNIQUE(version_id, preflight_id);
ALTER TABLE problem_versions ADD CONSTRAINT fk_versions_published_preflight
FOREIGN KEY(version_id, published_preflight_id) REFERENCES preflight_runs(version_id, preflight_id);
