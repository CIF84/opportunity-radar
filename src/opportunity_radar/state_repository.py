from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from opportunity_radar.change_detection import compare_material, fingerprint, material, snapshot, stable_json
from opportunity_radar.state_models import DetailObservation, SourceOutcome


SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETED','PARTIAL','FAILED'))
);
CREATE TABLE IF NOT EXISTS source_observations (
  source_observation_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
  company_id TEXT NOT NULL,
  adapter TEXT NOT NULL,
  status TEXT NOT NULL,
  expected_count INTEGER,
  observed_count INTEGER NOT NULL,
  inventory_complete INTEGER NOT NULL CHECK(inventory_complete IN (0,1)),
  details_complete INTEGER NOT NULL CHECK(details_complete IN (0,1)),
  detail_success_count INTEGER NOT NULL,
  detail_failure_count INTEGER NOT NULL,
  error_type TEXT,
  error_message TEXT,
  observed_at TEXT NOT NULL,
  UNIQUE(run_id, company_id)
);
CREATE TABLE IF NOT EXISTS job_instances (
  job_instance_id INTEGER PRIMARY KEY,
  company_id TEXT NOT NULL,
  external_job_id TEXT,
  canonical_url TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('ACTIVE','CLOSED')),
  current_fingerprint TEXT,
  latest_observation_id INTEGER REFERENCES job_observations(job_observation_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_external
  ON job_instances(company_id, external_job_id) WHERE external_job_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_url_fallback
  ON job_instances(company_id, canonical_url) WHERE external_job_id IS NULL;
CREATE TABLE IF NOT EXISTS job_observations (
  job_observation_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
  job_instance_id INTEGER NOT NULL REFERENCES job_instances(job_instance_id),
  observed_at TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  material_json TEXT NOT NULL,
  normalized_snapshot TEXT NOT NULL,
  UNIQUE(run_id, job_instance_id)
);
CREATE TABLE IF NOT EXISTS events (
  event_id INTEGER PRIMARY KEY,
  job_instance_id INTEGER NOT NULL REFERENCES job_instances(job_instance_id),
  run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  change_data TEXT,
  UNIQUE(run_id, job_instance_id, event_type)
);
CREATE TABLE IF NOT EXISTS candidate_profiles (
  candidate_profile_row_id INTEGER PRIMARY KEY,
  profile_id TEXT NOT NULL,
  profile_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  full_profile_fingerprint TEXT NOT NULL,
  semantic_profile_fingerprint TEXT NOT NULL,
  scoring_preference_fingerprint TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  UNIQUE(profile_id, profile_version)
);
CREATE TABLE IF NOT EXISTS semantic_assessments (
  semantic_assessment_id INTEGER PRIMARY KEY,
  job_instance_id INTEGER NOT NULL REFERENCES job_instances(job_instance_id),
  job_observation_id INTEGER REFERENCES job_observations(job_observation_id),
  content_fingerprint TEXT NOT NULL,
  candidate_profile_row_id INTEGER NOT NULL REFERENCES candidate_profiles(candidate_profile_row_id),
  semantic_profile_fingerprint TEXT NOT NULL,
  semantic_contract_version TEXT NOT NULL,
  assessor_id TEXT NOT NULL,
  assessor_version TEXT NOT NULL,
  assessment_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(job_instance_id, content_fingerprint, semantic_profile_fingerprint,
         semantic_contract_version, assessor_id, assessor_version)
);
CREATE TABLE IF NOT EXISTS opportunity_assessments (
  opportunity_assessment_id INTEGER PRIMARY KEY,
  job_instance_id INTEGER NOT NULL REFERENCES job_instances(job_instance_id),
  job_observation_id INTEGER REFERENCES job_observations(job_observation_id),
  candidate_profile_row_id INTEGER NOT NULL REFERENCES candidate_profiles(candidate_profile_row_id),
  semantic_assessment_id INTEGER REFERENCES semantic_assessments(semantic_assessment_id),
  scoring_preference_fingerprint TEXT NOT NULL,
  scoring_config_version TEXT NOT NULL,
  eligibility_json TEXT NOT NULL,
  features_json TEXT NOT NULL,
  triage_score INTEGER NOT NULL,
  composite_score REAL,
  core_dimension_coverage REAL NOT NULL,
  assessment_confidence TEXT,
  recommendation TEXT NOT NULL,
  missing_dimensions_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(job_instance_id, job_observation_id, candidate_profile_row_id,
         semantic_assessment_id, scoring_preference_fingerprint, scoring_config_version)
);
"""


class StateRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def create_run(self, run_id: str, started_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO ingestion_runs(run_id, started_at, status) VALUES (?,?, 'RUNNING')",
                (run_id, started_at),
            )

    def finish_run(self, run_id: str, completed_at: str, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE ingestion_runs SET completed_at=?, status=? WHERE run_id=?",
                (completed_at, status, run_id),
            )

    @contextmanager
    def source_transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _insert_source(connection, run_id: str, outcome: SourceOutcome) -> bool:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO source_observations(
              run_id, company_id, adapter, status, expected_count, observed_count,
              inventory_complete, details_complete, detail_success_count,
              detail_failure_count, error_type, error_message, observed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, outcome.company_id, outcome.adapter, outcome.status,
             outcome.expected_count, outcome.observed_count, outcome.inventory_complete,
             outcome.details_complete, outcome.detail_success_count,
             outcome.detail_failure_count, outcome.error_type, outcome.error_message,
             outcome.observed_at.isoformat()),
        )
        return cursor.rowcount == 1

    def record_failure(self, run_id: str, outcome: SourceOutcome) -> None:
        with self.connect() as connection:
            self._insert_source(connection, run_id, outcome)

    @staticmethod
    def _identity(reference) -> tuple[str, str]:
        if reference.external_job_id is not None:
            return "external", str(reference.external_job_id)
        return "url", reference.canonical_url

    @staticmethod
    def _find_job(connection, company_id: str, reference):
        if reference.external_job_id is not None:
            return connection.execute(
                "SELECT * FROM job_instances WHERE company_id=? AND external_job_id=?",
                (company_id, str(reference.external_job_id)),
            ).fetchone()
        return connection.execute(
            "SELECT * FROM job_instances WHERE company_id=? AND external_job_id IS NULL AND canonical_url=?",
            (company_id, reference.canonical_url),
        ).fetchone()

    @staticmethod
    def _event(connection, run_id, job_id, event_type, occurred_at, data=None):
        connection.execute(
            "INSERT OR IGNORE INTO events(job_instance_id,run_id,event_type,occurred_at,change_data) VALUES (?,?,?,?,?)",
            (job_id, run_id, event_type, occurred_at, stable_json(data) if data is not None else None),
        )

    def apply_outcome(self, run_id: str, outcome: SourceOutcome) -> None:
        with self.source_transaction() as connection:
            if not self._insert_source(connection, run_id, outcome):
                return
            if outcome.status != "SUCCESS" or not outcome.inventory_complete:
                return
            at = outcome.observed_at.isoformat()
            detail_by_identity = {
                self._identity(item.reference): item for item in outcome.details
            }
            present_ids: set[int] = set()
            for reference in outcome.references:
                existing = self._find_job(connection, outcome.company_id, reference)
                detail = detail_by_identity.get(self._identity(reference))
                if existing is None and detail is None:
                    continue
                if existing is None:
                    fp = fingerprint(detail.job)
                    cursor = connection.execute(
                        """INSERT INTO job_instances(company_id,external_job_id,canonical_url,
                           first_seen_at,last_seen_at,lifecycle_state,current_fingerprint)
                           VALUES (?,?,?,?,?,'ACTIVE',?)""",
                        (outcome.company_id, reference.external_job_id,
                         reference.canonical_url, at, at, fp),
                    )
                    job_id = cursor.lastrowid
                    self._event(connection, run_id, job_id, "NEW", at)
                else:
                    job_id = existing["job_instance_id"]
                    present_ids.add(job_id)
                    if existing["lifecycle_state"] == "CLOSED":
                        connection.execute(
                            "UPDATE job_instances SET lifecycle_state='ACTIVE',last_seen_at=? WHERE job_instance_id=?",
                            (at, job_id),
                        )
                        self._event(connection, run_id, job_id, "REOPENED", at)
                    else:
                        connection.execute(
                            "UPDATE job_instances SET last_seen_at=? WHERE job_instance_id=?",
                            (at, job_id),
                        )
                present_ids.add(job_id)
                if detail is None:
                    continue
                fp = fingerprint(detail.job)
                new_material = material(detail.job)
                old_observation = connection.execute(
                    "SELECT material_json FROM job_observations WHERE job_observation_id=(SELECT latest_observation_id FROM job_instances WHERE job_instance_id=?)",
                    (job_id,),
                ).fetchone()
                if old_observation:
                    for change in compare_material(json.loads(old_observation["material_json"]), new_material):
                        self._event(connection, run_id, job_id, change.event_type, at, {"old": change.old, "new": change.new})
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO job_observations(
                       run_id,job_instance_id,observed_at,fingerprint,material_json,normalized_snapshot
                       ) VALUES (?,?,?,?,?,?)""",
                    (run_id, job_id, at, fp, stable_json(new_material), snapshot(detail.job)),
                )
                observation = connection.execute(
                    "SELECT job_observation_id FROM job_observations WHERE run_id=? AND job_instance_id=?",
                    (run_id, job_id),
                ).fetchone()
                connection.execute(
                    """UPDATE job_instances SET current_fingerprint=?,latest_observation_id=?,
                       canonical_url=? WHERE job_instance_id=?""",
                    (fp, observation["job_observation_id"],
                     reference.canonical_url if reference.external_job_id is not None else existing["canonical_url"] if existing else reference.canonical_url,
                     job_id),
                )
            active = connection.execute(
                "SELECT job_instance_id FROM job_instances WHERE company_id=? AND lifecycle_state='ACTIVE'",
                (outcome.company_id,),
            ).fetchall()
            for row in active:
                job_id = row["job_instance_id"]
                if job_id not in present_ids:
                    connection.execute(
                        "UPDATE job_instances SET lifecycle_state='CLOSED' WHERE job_instance_id=?",
                        (job_id,),
                    )
                    self._event(connection, run_id, job_id, "CLOSED", at)

    def rows(self, table: str):
        if table not in {"ingestion_runs", "source_observations", "job_instances", "job_observations", "events", "candidate_profiles", "semantic_assessments", "opportunity_assessments"}:
            raise ValueError(table)
        with self.connect() as connection:
            return connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
