"""ReporterAgent — スタンプ生成結果を管理者へメール通知"""

import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from scripts.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK,
)


def _build_body(run_id: str, research: dict, design: dict, legal_result: tuple) -> str:
    l_passed, l_reason, l_flagged = legal_result
    char = design.get("character", {})
    prompts = design.get("prompts", [])

    generated = [p for p in prompts if p.get("image_path")]
    skipped   = [p for p in prompts if not p.get("image_path")]

    lines = [
        f"St.NEA LINEスタンプ自動生成レポート",
        f"実行日時：{datetime.now().strftime('%Y/%m/%d %H:%M')}",
        f"Run ID：{run_id}",
        "=" * 60,
        "",
        "■ 市場リサーチサマリー",
        research.get("market_summary", ""),
        "",
        f"■ 採用コンセプト",
        research.get("concept", ""),
        f"選定理由：{research.get('rationale', '')}",
        "",
        "■ キャラクター設定",
        f"  種別：{char.get('species', '')}",
        f"  カラー：{char.get('color', '')}",
        f"  性格：{char.get('personality', '')}",
        f"  画風：{char.get('style', '')}",
        f"  世界観：{char.get('world', '')}",
        "",
        "■ 生成画像",
        f"  生成完了：{len(generated)}枚 / スキップ：{len(skipped)}枚",
    ]

    if skipped:
        lines.append(f"  ※スキップ理由：OpenAI APIキー未設定 or 生成エラー")

    lines += [
        "",
        "■ リーガルチェック結果",
        f"  判定：{'OK ✓' if l_passed else 'NG ✗'}",
        f"  理由：{l_reason}",
    ]
    if l_flagged:
        lines.append(f"  NGパターン：{l_flagged}")

    lines += [
        "",
        "■ 管理者アクション",
        "  画像を確認し、メールに返信してください：",
        "  GO  → このまま申請に進む",
        "  NG  → 理由を添えて返信（次回改善に反映）",
        "  HOLD → 保留（次回再生成）",
        "",
        "---",
        "本メールはSt.NEA配信システムにより自動送信されています。",
    ]

    return "\n".join(lines)


def _send(subject: str, body: str, attachments: list):
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[Reporter] SMTP未設定 — コンソール出力のみ")
        print(subject)
        print(body)
        return

    recipients = [r for r in [ADMIN_EMAIL_PRIMARY, ADMIN_EMAIL_FALLBACK] if r]
    for recipient in recipients:
        try:
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"]    = SMTP_USER
            msg["To"]      = recipient
            msg.attach(MIMEText(body, "plain", "utf-8"))

            for filepath in attachments:
                p = Path(filepath)
                if p.exists():
                    with open(p, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
                    msg.attach(part)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, recipient, msg.as_string())

            print(f"[Reporter] メール送信完了 → {recipient}（添付：{len(attachments)}枚）")
            return
        except Exception as e:
            print(f"[Reporter][WARN] 送信失敗 ({recipient}): {e}")


def report(run_id: str, research: dict, design: dict, legal_result: tuple):
    l_passed = legal_result[0]
    subject = f"[St.NEA] スタンプ生成完了 {'✓' if l_passed else '要確認'} — {datetime.now().strftime('%Y/%m/%d')}"
    body = _build_body(run_id, research, design, legal_result)

    # 生成済み画像を添付
    attachments = [
        p["image_path"]
        for p in design.get("prompts", [])
        if p.get("image_path")
    ]

    _send(subject, body, attachments)
