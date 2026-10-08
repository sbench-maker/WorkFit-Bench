CREATE TABLE search_rebuild_jobs (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES projects(id),
  state text NOT NULL CHECK (state IN ('queued', 'running', 'complete', 'failed')),
  available_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX search_rebuild_jobs_claim_idx
  ON search_rebuild_jobs (available_at, id)
  WHERE state = 'queued';

-- Down migration drops search_rebuild_jobs after its worker and flag are disabled.
