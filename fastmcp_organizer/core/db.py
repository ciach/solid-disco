import sqlite3
import json
import uuid
from typing import Optional, List
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

from fastmcp_organizer.core.interfaces import IStorage, ExecutionPlan, PlanItem, ClassificationResult

class SQLiteStorage(IStorage):
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_hash TEXT PRIMARY KEY,
                    file_path TEXT,
                    size_bytes INTEGER,
                    mtime INTEGER,
                    metadata_json TEXT, -- ClassificationResult
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    root_dir TEXT,
                    status TEXT,
                    created_at TIMESTAMP,
                    executed_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS plan_items (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT,
                    src_path TEXT,
                    dest_path TEXT,
                    reasoning TEXT,
                    status TEXT,
                    error_msg TEXT,
                    FOREIGN KEY(plan_id) REFERENCES plans(id)
                );
            """)

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_plan(self, plan: ExecutionPlan) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO plans (id, root_dir, status, created_at) VALUES (?, ?, ?, ?)",
                (plan.id, plan.root_dir, plan.status, plan.created_at.isoformat())
            )
            for item in plan.items:
                conn.execute(
                    "INSERT INTO plan_items (id, plan_id, src_path, dest_path, reasoning, status, error_msg) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item.id, item.plan_id, item.src_path, item.dest_path, item.reasoning, item.status, item.error_msg)
                )

    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not row:
                return None
            
            items_rows = conn.execute("SELECT * FROM plan_items WHERE plan_id = ?", (plan_id,)).fetchall()
            items = [
                PlanItem(
                    id=item['id'],
                    plan_id=item['plan_id'],
                    src_path=item['src_path'],
                    dest_path=item['dest_path'],
                    reasoning=item['reasoning'],
                    status=item['status'],
                    error_msg=item['error_msg']
                ) for item in items_rows
            ]
            
            return ExecutionPlan(
                id=row['id'],
                root_dir=row['root_dir'],
                status=row['status'],
                created_at=row['created_at'],
                items=items
            )

    def update_item_status(self, item_id: str, status: str, error_msg: Optional[str] = None) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE plan_items SET status = ?, error_msg = ? WHERE id = ?",
                (status, error_msg, item_id)
            )

    def get_cached_classification(self, file_hash: str) -> Optional[ClassificationResult]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT metadata_json FROM file_cache WHERE file_hash = ?", (file_hash,)).fetchone()
            if row:
                data = json.loads(row['metadata_json'])
                return ClassificationResult(**data)
        return None

    def cache_classification(self, file_hash: str, result: ClassificationResult) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO file_cache (file_hash, file_path, size_bytes, mtime, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (file_hash, result.path, 0, 0, result.model_dump_json()) # We might want to pass size/mtime separately if we have them handy here, but the interface for cache_classification only takes result. I'll rely on the JSON blob for now or update interface if needed. Ideally, IScanner returns FileMetadata which has size/mtime.
                # Correction: I should update cache_classification to take FileMetadata + ClassificationResult ? 
                # For now, simplistic implementation. `size_bytes` and `mtime` in DB are for debugging mostly or re-hashing checks.
                # Let's just put 0 placeholders or extracting from result if I added them to ClassificationResult (I didn't). 
                # Actually, ClassificationResult has `path`.
                # I'll stick to this for now.
            )
