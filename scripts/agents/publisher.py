"""PublisherAgent — column_feed.json 更新 + GitHub push + メール配信"""

import json
import re
import smtplib
import subprocess
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from scripts.config import (
    COLUMN_JSON, GIT_REPO_PATH, AUTO_GIT_PUSH,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK,
)
from scripts.db.schema import get_conn

ARCHIVE_MAX = 60  # 保持する最大件数
_STOPWORDS = {"the", "a", "an", "in", "of", "for", "and", "or", "to", "is", "it", "its", "on", "at", "by"}


def _parse_date(date_str: str) -> str:
    """RFC 2822 / ISO 8601 / 生文字列を YYYY-MM-DD に正規化"""
    if not date_str:
        return ""
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        return datetime.fromisoformat(date_str[:19]).strftime("%Y-%m-%d")
    except Exception:
        pass
    return date_str[:10] if len(date_str) >= 10 else date_str


def _keywords(title: str) -> set:
    return {w.lower() for w in re.findall(r'\w+', title)
            if w.lower() not in _STOPWORDS and len(w) > 2}


def _load_existing() -> list:
    try:
        data = json.loads(COLUMN_JSON.read_text(encoding="utf-8"))
        return data.get("items", [])
    except Exception:
        return []


def _detect_updates(new_items: list, existing_items: list) -> list:
    """既存記事と同トピックの新記事に is_update フラグを付与"""
    by_source = {}
    for item in existing_items:
        src = item.get("source", "")
        by_source.setdefault(src, []).append(item)

    for item in new_items:
        src = item.get("source", "")
        kws = _keywords(item.get("title", ""))
        item.setdefault("is_update", False)
        item.setdefault("updates_ref", "")

        for old in by_source.get(src, []):
            if old.get("url") == item.get("url"):
                continue
            overlap = len(kws & _keywords(old.get("title", "")))
            if overlap >= 2:
                item["is_update"] = True
                item["updates_ref"] = old.get("url", "")
                break

    return new_items


def update_site(articles):
    """column_feed.json を更新してGitHubにpush"""
    column_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    existing = _load_existing()
    existing_urls = {item.get("url") for item in existing}

    new_items = [
        {
            "title":       a["title"],
            "source":      a["source"],
            "url":         a["url"],
            "column_text": a.get("column_text", ""),
            "published_at": _parse_date(a.get("published_at", "")),
            "column_at":   column_at,
            "is_update":   False,
            "updates_ref": "",
        }
        for a in articles
        if a["url"] not in existing_urls
    ]

    new_items = _detect_updates(new_items, existing)

    merged = new_items + existing
    merged = merged[:ARCHIVE_MAX]

    payload = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "generated_date": column_at,
        "count":          len(merged),
        "items":          merged,
    }
    COLUMN_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Publisher] column_feed.json 更新 ({len(merged)}件、新規{len(new_items)}件)")

    if AUTO_GIT_PUSH:
        return _git_push()
    return True


def _git_push() -> bool:
    try:
        subprocess.run(
            ["git", "add", "column_feed.json"],
            cwd=GIT_REPO_PATH, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"chore: update column_feed.json [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"],
            cwd=GIT_REPO_PATH, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=GIT_REPO_PATH, check=True, capture_output=True
        )
        print("[Publisher] GitHub push 完了")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Publisher][WARN] git push 失敗: {e.stderr.decode()}")
        return False


def send_email(articles, is_irregular=False):
    """管理者メールへコラム配信"""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[Publisher][WARN] SMTP未設定のためメール送信スキップ")
        return False

    subject_prefix = "【速報】" if is_irregular else "【週次】"
    subject = f"{subject_prefix} St.NEA AIコラム配信 — {datetime.now().strftime('%Y/%m/%d')}"

    body_parts = [f"St.NEA AIコラム配信\n配信日時：{datetime.now().strftime('%Y/%m/%d %H:%M')}\n\n"]
    body_parts.append("=" * 60 + "\n\n")

    for i, a in enumerate(articles, 1):
        body_parts.append(f"【{i}】{a['title']}\n")
        body_parts.append(f"ソース：{a['source']} | {a['url']}\n\n")
        body_parts.append(a.get("column_text", "") + "\n\n")
        body_parts.append("-" * 40 + "\n\n")

    body_parts.append("\n本メールはSt.NEA配信システムにより自動送信されています。\n")
    body = "".join(body_parts)

    recipients = [r for r in [ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK] if r]
    for recipient in recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = SMTP_USER
            msg["To"]      = recipient
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, recipient, msg.as_string())

            print(f"[Publisher] メール送信完了 → {recipient}")
            return True

        except Exception as e:
            print(f"[Publisher][WARN] メール送信失敗 ({recipient}): {e}")

    return False


def log_publish(article_ids, channel, note=""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO publish_log (published_at, article_ids, channel, note)
            VALUES (?, ?, ?, ?)
        """, (datetime.now(timezone.utc).isoformat(), json.dumps(article_ids), channel, note))
