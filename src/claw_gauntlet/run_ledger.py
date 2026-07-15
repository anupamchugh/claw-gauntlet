from dataclasses import dataclass
import json
from pathlib import Path

import duckdb

from claw_gauntlet.run_record import RunRecord


def _score_dimension(value: int, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError(f"{field} must be an integer from 0 to 100")
    return value


@dataclass(frozen=True)
class RunScore:
    run_id: str
    reliability: int
    resilience: int
    safety: int
    overall: int

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        for field in ("reliability", "resilience", "safety", "overall"):
            _score_dimension(getattr(self, field), field)


class RunLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.path))
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id VARCHAR PRIMARY KEY,
                claw_name VARCHAR NOT NULL,
                claw_version VARCHAR NOT NULL,
                outcome VARCHAR NOT NULL,
                created_at VARCHAR NOT NULL,
                record_json VARCHAR NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS runs_claw_idx ON runs(claw_name)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS runs_version_idx ON runs(claw_version)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS runs_outcome_idx ON runs(outcome)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS runs_created_idx ON runs(created_at)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                run_id VARCHAR PRIMARY KEY,
                reliability INTEGER NOT NULL,
                resilience INTEGER NOT NULL,
                safety INTEGER NOT NULL,
                overall INTEGER NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS baselines (
                claw_name VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL
            )
            """
        )

    def record_run(self, record: RunRecord) -> None:
        if not isinstance(record, RunRecord):
            raise TypeError("record must be a RunRecord")
        canonical = json.dumps(
            record.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        existing = self._connection.execute(
            "SELECT record_json FROM runs WHERE run_id = ?",
            [record.run_id],
        ).fetchone()
        if existing is not None:
            if existing[0] != canonical:
                raise ValueError(f"conflicting run payload for {record.run_id}")
            return
        self._connection.execute(
            """
            INSERT INTO runs (
                run_id, claw_name, claw_version, outcome, created_at, record_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                record.run_id,
                record.claw_name,
                record.claw_version,
                record.outcome,
                record.created_at,
                canonical,
            ],
        )

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._connection.execute(
            "SELECT record_json FROM runs WHERE run_id = ?",
            [run_id],
        ).fetchone()
        if row is None:
            return None
        return RunRecord.from_dict(json.loads(row[0]))

    def record_score(self, score: RunScore) -> None:
        if not isinstance(score, RunScore):
            raise TypeError("score must be a RunScore")
        if self.get_run(score.run_id) is None:
            raise ValueError(f"cannot score missing run {score.run_id}")
        self._connection.execute(
            """
            INSERT INTO scores VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (run_id) DO UPDATE SET
                reliability = excluded.reliability,
                resilience = excluded.resilience,
                safety = excluded.safety,
                overall = excluded.overall
            """,
            [
                score.run_id,
                score.reliability,
                score.resilience,
                score.safety,
                score.overall,
            ],
        )

    def get_score(self, run_id: str) -> RunScore | None:
        row = self._connection.execute(
            """
            SELECT run_id, reliability, resilience, safety, overall
            FROM scores WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
        if row is None:
            return None
        return RunScore(*row)

    def set_baseline(self, claw_name: str, run_id: str) -> None:
        row = self._connection.execute(
            "SELECT claw_name FROM runs WHERE run_id = ?",
            [run_id],
        ).fetchone()
        if row is None:
            raise ValueError(f"cannot set baseline for missing run {run_id}")
        if row[0] != claw_name:
            raise ValueError("baseline claw name must match the recorded run")
        self._connection.execute(
            """
            INSERT INTO baselines VALUES (?, ?)
            ON CONFLICT (claw_name) DO UPDATE SET run_id = excluded.run_id
            """,
            [claw_name, run_id],
        )

    def get_baseline(self, claw_name: str) -> str | None:
        row = self._connection.execute(
            "SELECT run_id FROM baselines WHERE claw_name = ?",
            [claw_name],
        ).fetchone()
        return None if row is None else row[0]

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "RunLedger":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
