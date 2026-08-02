"""QAAgent — 読者目線でコラム品質を毎日チェックし管理者に報告"""

import json
from datetime import datetime, date, timezone
from pathlib import Path

import anthropic

from scripts.config import ANTHROPIC_API_KEY, COLUMN_JSON
from scripts.agents import reporter as rep

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

FRESHNESS_WARN_DAYS = 14   # 掲載から何日で「古い」と判定するか
MIN_BODY_LENGTH = 100       # コラム本文の最小文字数


def _load_feed() -> list:
    try:
        data = json.loads(COLUMN_JSON.read_text(encoding="utf-8"))
        return data.get("items", [])
    except Exception:
        return []


def _structural_check(items: list) -> list:
    """タイトル・日付・本文長などの構造的チェック"""
    issues = []
    today = date.today()

    source_counts: dict = {}
    for item in items:
        src = item.get("source", "不明")
        source_counts[src] = source_counts.get(src, 0) + 1

    dominant = [(src, cnt) for src, cnt in source_counts.items() if cnt >= 3]

    for i, item in enumerate(items):
        title = item.get("title", "")
        column_text = item.get("column_text", "")
        published_at = item.get("published_at", "")
        column_at = item.get("column_at", "")

        if not title or title == item.get("url", ""):
            issues.append(f"[{i+1}] タイトル欠損: {item.get('url', '')[:60]}")

        if len(column_text) < MIN_BODY_LENGTH:
            issues.append(f"[{i+1}] 本文が短すぎる ({len(column_text)}文字): {title[:40]}")

        if not published_at:
            issues.append(f"[{i+1}] 元記事日付なし: {title[:40]}")

        if column_at:
            try:
                col_date = date.fromisoformat(column_at)
                age = (today - col_date).days
                if age > FRESHNESS_WARN_DAYS:
                    issues.append(f"[{i+1}] 掲載から{age}日経過（要更新確認）: {title[:40]}")
            except Exception:
                pass

    if dominant:
        for src, cnt in dominant:
            issues.append(f"ソース偏り: {src} が {cnt}件（多様性低下の恐れ）")

    return issues


def _qualitative_check(items: list) -> str:
    """Claude Haiku で読者目線の定性チェック"""
    if not items:
        return ""

    sample = items[:5]
    summaries = "\n".join(
        f"{i+1}. 【{s.get('source','')}】{s.get('title','')} — {s.get('column_text','')[:80]}..."
        for i, s in enumerate(sample)
    )

    prompt = f"""あなたはSt.NEAのコンテンツ品質管理担当です。
以下は現在Webサイトに掲載中のAIコラム（最新5件）の概要です。
読者目線で品質をチェックし、改善すべき点があれば3点以内で具体的に指摘してください。
問題がなければ「品質良好」とだけ返してください。

掲載コラム概要：
{summaries}

出力形式（箇条書き、日本語、1点あたり30字以内）：
- 指摘1
- 指摘2（あれば）"""

    try:
        res = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.content[0].text.strip()
    except Exception as e:
        return f"（定性チェックAPIエラー: {e}）"


def run() -> dict:
    """QAチェック実行。問題があれば管理者レポートを出力する。"""
    print("[QA] チェック開始")
    items = _load_feed()

    if not items:
        print("[QA] column_feed.json が空またはなし — スキップ")
        return {"status": "skipped", "issues": 0}

    struct_issues = _structural_check(items)
    qualitative = _qualitative_check(items)

    has_issues = bool(struct_issues) or (qualitative and "品質良好" not in qualitative)

    # コンソール出力
    print(f"[QA] 構造チェック：{len(struct_issues)}件の指摘")
    for iss in struct_issues:
        print(f"  ⚠ {iss}")

    print(f"[QA] 定性チェック：{qualitative}")

    if has_issues:
        _send_report(items, struct_issues, qualitative)

    print(f"[QA] 完了 — {'問題あり' if has_issues else '問題なし'}")
    return {
        "status": "issues" if has_issues else "ok",
        "structural": len(struct_issues),
        "qualitative": qualitative,
    }


def _send_report(items: list, struct_issues: list, qualitative: str):
    """管理者レポート送信（SMTP未設定時はコンソール出力）"""
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
    lines = [
        f"St.NEA コラム品質チェックレポート",
        f"実行日時：{now_str}",
        f"掲載件数：{len(items)}件",
        "=" * 60,
        "",
    ]

    if struct_issues:
        lines.append("■ 構造的な問題")
        for iss in struct_issues:
            lines.append(f"  ⚠ {iss}")
        lines.append("")

    lines += [
        "■ 読者目線チェック（Claude Haiku）",
        qualitative,
        "",
        "■ 対応方法",
        "  問題を確認し、必要であればパイプラインを再実行してください：",
        "  cd ~/stnea-official && python3 -m scripts.pipeline",
        "",
        "---",
        "本レポートはSt.NEA QAエージェントが自動生成しました。",
    ]
    body = "\n".join(lines)

    rep._send_admin(
        subject=f"[St.NEA QA] コラム品質レポート — {now_str}",
        body=body,
    )
