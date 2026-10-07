ALTER TABLE predictions
ADD COLUMN algorithm_version VARCHAR(64)
DEFAULT 'FRIE-6D-v1.0';

ALTER TABLE predictions
ADD COLUMN frie_maximum FLOAT
DEFAULT 600.0;

ALTER TABLE predictions
ADD COLUMN scoring_profile VARCHAR(16)
DEFAULT 'neutral';

ALTER TABLE predictions
ADD COLUMN dimensions_json TEXT
DEFAULT '{}';

ALTER TABLE predictions
ADD COLUMN overall_coverage FLOAT;

ALTER TABLE predictions
ADD COLUMN overall_confidence VARCHAR(16);