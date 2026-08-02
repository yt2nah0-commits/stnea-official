"""GeneratorAgent — gpt-image-1で画像生成（OpenAI APIキー取得後に有効化）"""

import os
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def generate(prompts: list, run_id: str) -> list:
    """
    OpenAI APIキーが設定されていない場合はプレースホルダーを返す。

    Returns:
        prompts: image_path が埋まった状態のリスト
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[Generator] OPENAI_API_KEY 未設定 — 画像生成をスキップ（プレースホルダー）")
        for p in prompts:
            p["image_path"] = None
            p["skipped"]    = True
        return prompts

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        run_dir = OUTPUT_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        for p in prompts:
            try:
                response = client.images.generate(
                    model="gpt-image-1",
                    prompt=p["prompt"],
                    n=1,
                    size="1024x1024",   # gpt-image-1の最小サイズ（後でリサイズ）
                    response_format="b64_json",
                )
                import base64
                from PIL import Image
                import io

                img_data = base64.b64decode(response.data[0].b64_json)
                img = Image.open(io.BytesIO(img_data))
                img = img.resize((370, 320), Image.LANCZOS)

                filename = f"stamp_{p['pattern_id']:02d}_{p['emotion']}.png"
                filepath = run_dir / filename
                img.save(filepath, "PNG")

                p["image_path"] = str(filepath)
                p["skipped"]    = False
                print(f"[Generator] 生成完了：{filename}")

            except Exception as e:
                print(f"[Generator][WARN] パターン{p['pattern_id']}生成失敗: {e}")
                p["image_path"] = None
                p["skipped"]    = True

    except ImportError:
        print("[Generator][WARN] openai/Pillow 未インストール — pip install openai Pillow")
        for p in prompts:
            p["image_path"] = None
            p["skipped"]    = True

    return prompts
