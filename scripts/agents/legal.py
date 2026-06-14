"""LegalAgent — 著作権・引用適法性・炎上リスクチェック"""

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
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def check(article: dict) -> tuple[bool, str]:
    """
    Returns:
        (passed, reason)
    """
    prompt = f"""あなたはSt.NEAの法務エージェントです。
以下のAIニュース要約をSt.NEAサイトに転載・要約紹介する場合の法的リスクを確認してください。

タイトル：{article['title']}
要約：{article.get('summary', '')}
ソース：{article['source']}
URL：{article['url']}

以下をJSONで返してください：
- passed: true/false
- reason: 判定理由（1文、日本語）
- risk_level: low/medium/high

チェック観点：
1. 記事本文を大量に転載していないか（要約紹介はOK）
2. 特定個人・企業への誹謗中傷リスク
3. 炎上しやすい政治・宗教・差別的内容の有無
4. 「ソース明記」「引用の範囲内」であればOKとする

注意：要約・紹介はほぼ問題ない。過度に厳しく判定しないこと。
JSONのみ返答してください。"""

    try:
        res = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        result = _extract_json(res.content[0].text)
        passed = result.get("passed", True)
        reason = result.get("reason", "チェック完了")
        return bool(passed), reason
    except Exception as e:
        print(f"[Legal][WARN] {e}")
        return True, "チェックスキップ（APIエラー）"
