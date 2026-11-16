
CREATE TABLE gate_anomalies (
	id INTEGER NOT NULL AUTO_INCREMENT,
	verification_id INTEGER,
	kind VARCHAR(20),
	ticket VARCHAR(60),
	happened_at VARCHAR(40),
	reason VARCHAR(300),
	device VARCHAR(40),
	event_no VARCHAR(40),
	PRIMARY KEY (id),
	FOREIGN KEY(verification_id) REFERENCES verifications (id)
)
;

CREATE INDEX ix_gate_anomalies_verification_id ON gate_anomalies (verification_id)
;


CREATE TABLE gate_events (
	id INTEGER NOT NULL AUTO_INCREMENT,
	device VARCHAR(40) NOT NULL,
	event_no VARCHAR(40) NOT NULL,
	ticket VARCHAR(60),
	session VARCHAR(60),
	happened_at VARCHAR(40),
	action VARCHAR(8),
	received_at VARCHAR(40),
	PRIMARY KEY (id),
	UNIQUE (device, event_no)
)
;

CREATE INDEX ix_gate_events_session ON gate_events (session)
;


CREATE TABLE presence_intervals (
	id INTEGER NOT NULL AUTO_INCREMENT,
	verification_id INTEGER,
	ticket VARCHAR(60),
	entered_at VARCHAR(40),
	exited_at VARCHAR(40),
	PRIMARY KEY (id),
	FOREIGN KEY(verification_id) REFERENCES verifications (id)
)
;

CREATE INDEX ix_presence_intervals_verification_id ON presence_intervals (verification_id)
;


CREATE TABLE verifications (
	id INTEGER NOT NULL AUTO_INCREMENT,
	session VARCHAR(60) NOT NULL,
	state VARCHAR(20),
	input_version INTEGER,
	computed_version INTEGER,
	retry_count INTEGER,
	result JSON,
	error TEXT,
	created VARCHAR(40),
	updated VARCHAR(40),
	PRIMARY KEY (id),
	UNIQUE (session)
)
;


ALTER TABLE settlements ADD COLUMN manual_checked INTEGER
;

ALTER TABLE settlements ADD COLUMN verification_id INTEGER
;
