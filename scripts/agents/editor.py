"""EditorAgent — 編集長。Writerのコラムを配信前に推敲・品質チェック"""

import json
import re

import anthropic

from scripts.config import ANTHROPIC_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _extract_json(text: str) -> dict:
    # revised_text が長文になるため、最初の { から最後の } まで貪欲にマッチさせる
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


REVIEW_TEMPLATE = """あなたはSt.NEAの編集長エージェントです。
ライターが書いた以下のコラムを配信前レビューしてください。

■ 元記事
タイトル：{title}
要約：{summary}
ソース：{source}
URL：{url}

■ コラム原稿
{column_text}

チェック観点：
1. フォーマット遵守（【タイトル】→ 📌リード文 → 本文 → 🔗ソース の順になっているか）
2. タイトルは日本語30〜40字、本文は200〜300字程度か
3. 禁止表現（「革命的」「ヤバい」「完全自動化」）を使っていないか
4. 断言しすぎていないか（「〜とみられます」「〜の可能性があります」調か）
5. 読者がすぐ試せるヒントが1つ含まれているか
6. 元記事の内容から逸脱・捏造していないか
7. 文末が「。」で統一されているか

判定ルール：
- 問題なし → passed: true、revised_text: null
- 軽微な問題（表現・体裁・文字数）→ あなた自身が推敲して修正版を作り、passed: true、revised_text に修正版全文
- 修正不能な問題（内容の捏造・元記事との重大な乖離）→ passed: false、revised_text: null

以下をJSONで返してください：
- passed: true/false
- reason: 判定理由（1文、日本語）
- revised_text: 修正版全文 または null

JSONのみ返答してください。"""


def review(article: dict, column_text: str):
    """
    Returns:
        (passed, reason, revised_text)
        passed=True  → revised_text があればそちらを配信、なければ原稿のまま配信
        passed=False → 差し戻し（NG扱い、修正可能として再キュー候補）
    """
    prompt = REVIEW_TEMPLATE.format(
        title=article["title"],
        summary=article.get("summary", ""),
        source=article["source"],
        url=article["url"],
        column_text=column_text,
    )
    try:
        res = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        result = _extract_json(res.content[0].text)
        passed = bool(result.get("passed", True))
        reason = result.get("reason", "レビュー完了")
        revised = result.get("revised_text") or None
        if revised is not None and not isinstance(revised, str):
            revised = None
        return passed, reason, revised
    except Exception as e:
        print(f"[Editor][WARN] {e}")
        return True, "レビュースキップ（APIエラー）", None
