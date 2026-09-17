"""Deployment history, persisted to a local SQLite database."""
import datetime
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    trigger_source TEXT NOT NULL,
    commit_before TEXT,
    commit_after TEXT,
    success INTEGER NOT NULL,
    rolled_back INTEGER NOT NULL DEFAULT 0,
    output TEXT
)
"""

COLUMNS = [
    "id",
    "timestamp",
    "trigger_source",
    "commit_before",
    "commit_after",
    "success",
    "rolled_back",
    "output",
]


class DeploymentHistory:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._connect()
        try:
            conn.execute(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        trigger_source,
        commit_before,
        commit_after,
        success,
        output="",
        rolled_back=False,
    ):
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO deployments "
                "(timestamp, trigger_source, commit_before, commit_after, "
                "success, rolled_back, output) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    trigger_source,
                    commit_before,
                    commit_after,
                    1 if success else 0,
                    1 if rolled_back else 0,
                    output,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def recent(self, limit=10):
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT {} FROM deployments ORDER BY id DESC LIMIT ?".format(
                    ", ".join(COLUMNS)
                ),
                (limit,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [dict(zip(COLUMNS, row)) for row in rows]
