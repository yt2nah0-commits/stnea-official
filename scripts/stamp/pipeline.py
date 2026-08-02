"""
St.NEA LINEスタンプ自動生成パイプライン
実行方法：
  python -m scripts.stamp.pipeline          # 即時実行
  python -m scripts.stamp.pipeline --schedule  # スケジューラ起動
"""

import argparse
from datetime import datetime

from scripts.db.schema import init_db
from scripts.stamp.feedback_store import init_feedback_table
from scripts.stamp.agents import research, design, generator, legal, reporter


def run_pipeline() -> dict:
    run_id = datetime.now().strftime("stamp_%Y%m%d_%H%M")
    print(f"\n{'='*60}")
    print(f"[StampPipeline] 開始 — {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
    print(f"[StampPipeline] Run ID: {run_id}")
    print('='*60)

    # Step 1: 市場リサーチ
    research_result = research.research()

    # Step 2: キャラクター設定 + プロンプト生成
    design_result = design.design(research_result)

    # Step 3: 画像生成（OpenAI APIキーがあれば実行、なければスキップ）
    prompts = generator.generate(design_result["prompts"], run_id)
    design_result["prompts"] = prompts

    generated_count = sum(1 for p in prompts if p.get("image_path"))
    print(f"[StampPipeline] 画像生成：{generated_count}/8枚")

    # Step 4: リーガルチェック
    legal_result = legal.check(design_result["character"], prompts)

    # Step 5: 管理者通知
    reporter.report(run_id, research_result, design_result, legal_result)

    print(f"[StampPipeline] 完了 — {run_id}")
    print('='*60 + "\n")

    return {
        "run_id":    run_id,
        "concept":   research_result.get("concept", ""),
        "generated": generated_count,
        "legal_ok":  legal_result[0],
    }


def start_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone="Asia/Tokyo")
    scheduler.add_job(
        run_pipeline,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="stamp_weekly",
        name="スタンプ週次生成（月曜08:00）",
    )
    print("[StampScheduler] 起動 — 毎週月曜 08:00")
    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="St.NEA スタンプ自動生成パイプライン")
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()

    init_db()
    init_feedback_table()

    if args.schedule:
        start_scheduler()
    else:
        result = run_pipeline()
        print(f"実行結果：{result}")
