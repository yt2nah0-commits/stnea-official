"""ReporterAgent — 管理者通知（NG発生・配信見送り）"""

import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from scripts.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK,
)


def _send(subject: str, body: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[Reporter][WARN] SMTP未設定 — コンソール出力のみ\n{subject}\n{body}")
        return

    for recipient in [r for r in [ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK] if r]:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"]    = SMTP_USER
            msg["To"]      = recipient

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, recipient, msg.as_string())

            print(f"[Reporter] 管理者通知送信 → {recipient}")
            return
        except Exception as e:
            print(f"[Reporter][WARN] 送信失敗 ({recipient}): {e}")


def report_ng(article: dict, ng_reason: str, ng_agent: str, fixable: bool):
    subject = f"[St.NEA] NG記事発生 — {article['title'][:30]}"
    fixable_str = "修正可能（鮮度期限内なら再キュー）" if fixable else "修正不可（アーカイブのみ）"
    body = f"""St.NEA パイプライン — NG記事通知
発生日時：{datetime.now().strftime('%Y/%m/%d %H:%M')}

■ 該当記事
タイトル：{article['title']}
URL：{article['url']}
ソース：{article['source']}

■ NG詳細
検出エージェント：{ng_agent}
NG理由：{ng_reason}
修正可否：{fixable_str}

---
本メールはSt.NEA配信システムにより自動送信されています。
"""
    _send(subject, body)


def report_no_articles():
    subject = "[St.NEA] 配信スキップ — 配信対象記事なし"
    body = f"""St.NEA パイプライン — 配信スキップ通知
発生日時：{datetime.now().strftime('%Y/%m/%d %H:%M')}

今回の収集で配信対象となる新規記事がありませんでした。
次回の定期収集まで待機します。

---
本メールはSt.NEA配信システムにより自動送信されています。
"""
    _send(subject, body)


def report_ng_rate_exceeded(total: int, passed: int, ng_rate: float):
    subject = f"[St.NEA] 配信見送り — NG率超過 ({ng_rate:.0%})"
    body = f"""St.NEA パイプライン — 配信見送り通知
発生日時：{datetime.now().strftime('%Y/%m/%d %H:%M')}

NG率が閾値（50%）を超えたため、今回の配信を見送りました。

■ 集計
収集記事数：{total}件
チェック通過：{passed}件
NG率：{ng_rate:.0%}

対象記事はすべてNG/アーカイブに移行されました。
次回配信時に修正可能なものは再キューされます。

---
本メールはSt.NEA配信システムにより自動送信されています。
"""
    _send(subject, body)
