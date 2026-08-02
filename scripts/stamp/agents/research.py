"""ResearchAgent — LINEスタンプ市場リサーチ（Web検索ベース）"""

import json
import re
import anthropic
from scripts.config import ANTHROPIC_API_KEY
from scripts.stamp.feedback_store import get_feedback_context

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

def research() -> dict:
    """
    Returns:
        {
          "market_summary": str,   # 市場傾向サマリー
          "concept": str,          # 推薦コンセプト
          "rationale": str,        # 選定理由
          "avoid": list[str],      # 避けるべきデザイン傾向
        }
    """
    feedback_ctx = get_feedback_context("stamp")
    feedback_section = ""
    if feedback_ctx:
        feedback_section = f"""
## 過去の管理者フィードバック（参照して方針を改善すること）
{feedback_ctx}
"""

    prompt = f"""あなたはSt.NEAのリサーチエージェントです。
LINEスタンプの市場動向を分析し、「被らないが好まれそう」なコンセプトを提案してください。

## 調査・分析の観点
1. 現在人気のスタンプカテゴリ傾向（人物・動物・架空生物・文字系など）
2. 売れ筋デザインの特徴（色味・タッチ・世界観・表情）
3. 飽和しているテーマ（避けるべきもの）
4. ニッチだが熱量のあるコミュニティ向けテーマ
5. AIクリエイターやデジタルツール愛好者に刺さりそうなテーマ
{feedback_section}

以下のJSONで返してください：
{{
  "market_summary": "市場傾向の要約（200字以内）",
  "concept": "推薦コンセプト（例：ゆるい宇宙人キャラが日常あるあるを呟く）",
  "rationale": "選定理由（なぜこれが今刺さるか・100字以内）",
  "avoid": ["避けるべきテーマ1", "避けるべきテーマ2"]
}}

JSONのみ返してください。"""

    try:
        res = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = res.content[0].text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            print(f"[Research] コンセプト決定：{result.get('concept', '')}")
            return result
    except Exception as e:
        print(f"[Research][WARN] {e}")

    return {
        "market_summary": "取得失敗",
        "concept": "ゆるい動物キャラが感情表現するスタンプ",
        "rationale": "安定した需要がある定番テーマをフォールバックとして採用",
        "avoid": [],
    }
