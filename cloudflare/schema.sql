CREATE TABLE IF NOT EXISTS deliveries (
  delivery_id TEXT PRIMARY KEY NOT NULL,
  event TEXT NOT NULL CHECK (event IN ('ping', 'check_suite')),
  payload_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'failed')),
  error TEXT,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  processed_at TEXT
);

CREATE INDEX IF NOT EXISTS deliveries_status_received_at
  ON deliveries (status, received_at);
