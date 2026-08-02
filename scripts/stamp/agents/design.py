"""DesignAgent — キャラクター設定 + gpt-image-1向けプロンプト生成"""

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

# 8パターンの表情・セリフ・ポーズ定義
STAMP_PATTERNS = [
    {"emotion": "喜び",     "pose": "両手を上げてジャンプ",   "text": "やったー！"},
    {"emotion": "感謝",     "pose": "深くお辞儀",              "text": "ありがとう"},
    {"emotion": "驚き",     "pose": "口を大きく開けて後退",    "text": "えっ！？"},
    {"emotion": "照れ",     "pose": "頬に手を当てて俯く",      "text": "///"},
    {"emotion": "困惑",     "pose": "頭を抱える",              "text": "どうしよう…"},
    {"emotion": "了解",     "pose": "親指を立てて笑顔",        "text": "OK！"},
    {"emotion": "眠い",     "pose": "目を半開きでふらふら",    "text": "zzz…"},
    {"emotion": "応援",     "pose": "腕を振って前傾姿勢",      "text": "がんばれ！"},
]

def design(research_result: dict) -> dict:
    """
    Returns:
        {
          "character": dict,        # キャラクター設定
          "prompts": list[dict],    # 8枚分のプロンプト
        }
    """
    feedback_ctx = get_feedback_context("stamp")
    feedback_section = f"\n## 過去フィードバック\n{feedback_ctx}" if feedback_ctx else ""

    concept   = research_result.get("concept", "ゆるい動物キャラ")
    rationale = research_result.get("rationale", "")
    avoid     = research_result.get("avoid", [])

    prompt = f"""あなたはSt.NEAのデザインエージェントです。
以下のコンセプトをもとに、LINEスタンプ用のキャラクター設定を作成してください。

## コンセプト
{concept}

## 選定理由
{rationale}

## 避けること
{', '.join(avoid) if avoid else 'なし'}
{feedback_section}

## 制約
- 既存の有名キャラクター・著作物に似せない
- シンプルで小さいサイズでも視認しやすいデザイン
- LINEスタンプの規格（370×320px・透過背景）に適した構図

以下のJSONで返してください：
{{
  "character": {{
    "species": "種別（例：丸い宇宙人）",
    "color": "メインカラー（例：パステルパープル）",
    "personality": "性格（例：マイペースでちょっと天然）",
    "style": "画風（例：ゆるふわ・線が太め・影なし）",
    "world": "世界観（例：日常の中にちょっと不思議な存在）"
  }},
  "base_prompt": "全スタンプ共通の基本プロンプト（英語・50語以内）"
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
            character_data = json.loads(match.group())
        else:
            raise ValueError("JSON parse failed")
    except Exception as e:
        print(f"[Design][WARN] キャラクター生成失敗: {e}")
        character_data = {
            "character": {"species": "丸いスライム", "color": "水色", "personality": "のんびり屋", "style": "ゆるふわ", "world": "日常"},
            "base_prompt": "cute round slime character, pastel blue, simple flat design, transparent background, LINE sticker style"
        }

    base_prompt = character_data.get("base_prompt", "")
    character   = character_data.get("character", {})

    # 8パターン分のプロンプトを構築
    prompts = []
    for p in STAMP_PATTERNS:
        full_prompt = (
            f"{base_prompt}, "
            f"{p['emotion']} expression, {p['pose']}, "
            f"with text bubble saying '{p['text']}', "
            f"LINE sticker, 370x320px, transparent background, "
            f"no existing IP characters, original design"
        )
        prompts.append({
            "pattern_id":  STAMP_PATTERNS.index(p) + 1,
            "emotion":     p["emotion"],
            "pose":        p["pose"],
            "text":        p["text"],
            "prompt":      full_prompt,
            "image_path":  None,   # GeneratorAgentが埋める
        })

    print(f"[Design] キャラクター設定完了：{character.get('species', '')} / 8プロンプト生成")
    return {"character": character, "prompts": prompts}
