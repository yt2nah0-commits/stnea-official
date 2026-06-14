"""ArchiveAgent — NG記事のアーカイブ・再キュー判定"""

from datetime import datetime, timezone, timedelta

from scripts.config import FRESHNESS_DAYS
from scripts.db.schema import get_conn


def archive_ng(article: dict, ng_reason: str, ng_agent: str, fixable: bool):
    """NG記事をアーカイブDBに保存し、articlesテーブルのステータスを更新"""
    now = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        conn.execute("""
            UPDATE articles SET status=?, ng_reason=?, ng_agent=?, fixable=?
            WHERE url=?
        """, ("ng" if not fixable else "queued", ng_reason, ng_agent, int(fixable), article["url"]))

        conn.execute("""
            INSERT INTO ng_archive (url, title, ng_reason, ng_agent, archived_at, fixable)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (article["url"], article["title"], ng_reason, ng_agent, now, int(fixable)))


def get_retry_queue() -> list[dict]:
    """鮮度期限内の修正可能NG記事を返す（次回配信候補）"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FRESHNESS_DAYS)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM articles
            WHERE status='queued' AND fixable=1 AND fetched_at >= ?
        """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def mark_queued_as_archived():
    """鮮度切れの再キュー記事をアーカイブのみに変更"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FRESHNESS_DAYS)).isoformat()
    with get_conn() as conn:
        conn.execute("""
            UPDATE articles SET status='archived'
            WHERE status='queued' AND fetched_at < ?
        """, (cutoff,))
