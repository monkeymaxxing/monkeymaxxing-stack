-- PostgreSQL is the durable job ledger. SQS carries only notifications.
ALTER TABLE report_jobs ADD COLUMN available_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE report_jobs ADD COLUMN sqs_notified_at timestamptz;
