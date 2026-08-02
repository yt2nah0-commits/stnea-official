"""LegalAgent — LINEガイドライン準拠・類似性チェック"""

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

LINE_GUIDELINES = """
LINEクリエイターズマーケット 主要禁止事項：
- 他社キャラクター・著名人・商標への類似
- 性的・暴力的・差別的表現
- 実在の政治家・宗教指導者の使用
- ギャンブル・薬物を助長する表現
- AI生成画像は「AI生成」ラベルが必須（2025年6月以降）
"""

def check(character: dict, prompts: list) -> tuple:
    """
    Returns:
        (passed, reason, flagged_patterns)
        flagged_patterns: NGになったpattern_idのリスト
    """
    char_desc = json.dumps(character, ensure_ascii=False)
    pattern_summary = json.dumps(
        [{"id": p["pattern_id"], "emotion": p["emotion"], "text": p["text"]} for p in prompts],
        ensure_ascii=False
    )

    prompt = f"""あなたはSt.NEAの法務エージェントです。
以下のLINEスタンプ設定がLINEクリエイターズマーケットのガイドラインに準拠しているか確認してください。

## ガイドライン要点
{LINE_GUIDELINES}

## キャラクター設定
{char_desc}

## プロンプト（8パターンの概要）
{pattern_summary}

以下のJSONで返してください：
{{
  "passed": true/false,
  "reason": "総合判定の理由（1文）",
  "flagged_patterns": [],
  "risk_level": "low/medium/high",
  "notes": "注意事項（AI生成ラベル必須など）"
}}

注意：オリジナルキャラクターで既存IPに似ていなければ基本的にOK。過度に厳しく判定しないこと。
JSONのみ返してください。"""

    try:
        res = _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        text = res.content[0].text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            passed  = result.get("passed", True)
            reason  = result.get("reason", "チェック完了")
            flagged = result.get("flagged_patterns", [])
            notes   = result.get("notes", "")
            print(f"[Legal] 判定：{'OK' if passed else 'NG'} — {reason}")
            if notes:
                print(f"[Legal] 注意：{notes}")
            return bool(passed), reason, flagged
    except Exception as e:
        print(f"[Legal][WARN] {e}")

    return True, "チェックスキップ（APIエラー）", []
