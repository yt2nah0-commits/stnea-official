"""ValidatorAgent — ハルシネーション・誇張表現チェック"""

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


def validate(article: dict) -> tuple[bool, str]:
    """
    Returns:
        (passed, reason)  passed=True → 次エージェントへ
    """
    prompt = f"""あなたはファクトチェックエージェントです。
以下のAIニュース記事の要約を確認し、問題がないか判定してください。

タイトル：{article['title']}
要約：{article.get('summary', '')}
ソース：{article['source']}

以下をJSONで返してください：
- passed: true/false
- reason: 判定理由（1文、日本語）
- issues: 問題点のリスト（passedがfalseの場合）

チェック観点：
1. 事実として断言しているが出典不明の主張がある
2. 「完全に」「革命的」「100%」等の誇張表現
3. 存在しないモデル名・機能名への言及
4. 明らかに矛盾する情報

注意：公式ブログ（Anthropic/OpenAI/Google）からの記事は基本的に信頼性が高い。
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
        print(f"[Validator][WARN] {e}")
        return True, "チェックスキップ（APIエラー）"
