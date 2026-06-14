"""PublisherAgent — column_feed.json 更新 + GitHub push + メール配信"""

import json
import smtplib
import subprocess
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from scripts.config import (
    COLUMN_JSON, GIT_REPO_PATH, AUTO_GIT_PUSH,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK,
)
from scripts.db.schema import get_conn


def update_site(articles: list[dict]) -> bool:
    """column_feed.json を更新してGitHubにpush"""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_at": now,
        "generated_date": datetime.now().strftime("%Y-%m-%d"),
        "count": len(articles),
        "items": [
            {
                "title":       a["title"],
                "source":      a["source"],
                "url":         a["url"],
                "column_text": a.get("column_text", ""),
                "published_at": now,
            }
            for a in articles
        ],
    }
    COLUMN_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Publisher] column_feed.json 更新 ({len(articles)}件)")

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


def send_email(articles: list[dict], is_irregular: bool = False) -> bool:
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

    for recipient in [ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK]:
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
            if recipient == ADMIN_EMAIL_PRIMARY:
                print("[Publisher] フォールバックアドレスへ再試行します")
                continue

    return False


def log_publish(article_ids: list[int], channel: str, note: str = ""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO publish_log (published_at, article_ids, channel, note)
            VALUES (?, ?, ?, ?)
        """, (datetime.now(timezone.utc).isoformat(), json.dumps(article_ids), channel, note))
