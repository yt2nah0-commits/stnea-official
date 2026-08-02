"""FeedbackAgent — メール返信の解析・DB記録

使い方：
  python -m scripts.stamp.feedback_agent --system stamp --verdict GO --ref "output/run_001"
  python -m scripts.stamp.feedback_agent --system column --verdict NG --reason "記事が古い" --ref "https://..."

メール返信の場合は IMAPで受信後、本スクリプトを自動呼び出しする（SMTP設定後に実装）。
現在は手動入力モードで動作。
"""

import argparse
import re
from scripts.stamp.feedback_store import record, get_feedback_context


def parse_email_body(body: str) -> tuple:
    """
    メール本文から verdict と reason を抽出する。
    対応フォーマット：
      1行目に "GO" / "NG" / "HOLD"（大小文字不問）
      2行目以降に理由（任意）
    """
    lines = [l.strip() for l in body.strip().splitlines() if l.strip()]
    if not lines:
        return None, ""

    first = lines[0].upper()
    verdict = None
    for v in ["GO", "NG", "HOLD"]:
        if v in first:
            verdict = v
            break

    reason = "\n".join(lines[1:]) if len(lines) > 1 else ""
    return verdict, reason


def main():
    parser = argparse.ArgumentParser(description="FeedbackAgent — 管理者判定を記録")
    parser.add_argument("--system",  required=True, choices=["stamp", "column"], help="対象システム")
    parser.add_argument("--verdict", required=True, help="GO / NG / HOLD")
    parser.add_argument("--ref",     required=True, help="対象アイテムの参照（run_id or URL）")
    parser.add_argument("--run-id",  default="",    help="ランID（スタンプ系）")
    parser.add_argument("--reason",  default="",    help="NG/HOLD理由（任意）")
    parser.add_argument("--show",    action="store_true", help="過去フィードバックを表示")
    args = parser.parse_args()

    if args.show:
        ctx = get_feedback_context(args.system)
        print(f"=== {args.system} フィードバック履歴 ===")
        print(ctx if ctx else "（記録なし）")
        return

    verdict = args.verdict.upper()
    if verdict not in ("GO", "NG", "HOLD"):
        print(f"[FeedbackAgent] エラー：verdict は GO / NG / HOLD のいずれかを指定してください")
        return

    record(
        system=args.system,
        run_id=args.run_id,
        item_ref=args.ref,
        verdict=verdict,
        reason=args.reason,
    )
    print(f"[FeedbackAgent] 記録完了 — {args.system} / {verdict}")


if __name__ == "__main__":
    main()
