"""FeedbackStore — 管理者判定の記録・参照（スタンプ・コラム共通）"""

import json
from datetime import datetime, timezone
from scripts.db.schema import get_conn


def init_feedback_table():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system      TEXT NOT NULL,   -- 'stamp' or 'column'
            run_id      TEXT,
            item_ref    TEXT,            -- 画像パス or 記事URL
            verdict     TEXT NOT NULL,   -- 'GO' / 'NG' / 'HOLD'
            reason      TEXT,
            recorded_at TEXT
        );
        """)


def record(system: str, run_id: str, item_ref: str, verdict: str, reason: str = ""):
    """管理者判定を記録"""
    init_feedback_table()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO feedback (system, run_id, item_ref, verdict, reason, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (system, run_id, item_ref, verdict.upper(), reason,
              datetime.now(timezone.utc).isoformat()))
    print(f"[Feedback] 記録 — {system} / {verdict} / {item_ref[:40]}")


def get_feedback_context(system: str, limit: int = 10) -> str:
    """過去のフィードバックをエージェントが参照できるテキストで返す"""
    init_feedback_table()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT verdict, reason, item_ref, recorded_at
            FROM feedback
            WHERE system=?
            ORDER BY recorded_at DESC
            LIMIT ?
        """, (system, limit)).fetchall()

    if not rows:
        return ""

    lines = []
    for r in rows:
        reason_str = f"（理由：{r['reason']}）" if r['reason'] else ""
        lines.append(f"- {r['verdict']}{reason_str} ← {r['item_ref'][:50]}")

    return "\n".join(lines)


def get_ng_patterns(system: str) -> list:
    """NGになったパターンの理由一覧（改善参照用）"""
    init_feedback_table()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT reason, item_ref FROM feedback
            WHERE system=? AND verdict='NG' AND reason != ''
            ORDER BY recorded_at DESC
            LIMIT 20
        """, (system,)).fetchall()
    return [{"reason": r["reason"], "ref": r["item_ref"]} for r in rows]
