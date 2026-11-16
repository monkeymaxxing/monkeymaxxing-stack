-- Additive: the previous release can still insert records without a description.
ALTER TABLE records ADD COLUMN description text NOT NULL DEFAULT '';
