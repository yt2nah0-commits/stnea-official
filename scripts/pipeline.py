"""
St.NEA AIコラム自動配信パイプライン
実行方法：
  python -m scripts.pipeline          # 即時実行（テスト用）
  python -m scripts.pipeline --schedule  # スケジューラ起動（常駐）
"""

import sys
import argparse
from datetime import datetime

from scripts.db.schema import init_db
from scripts.config import NG_RATE_THRESHOLD, WEEKLY_DAY, WEEKLY_HOUR, WEEKLY_MINUTE
from scripts.agents import collector, validator, legal, writer, editor, archive, publisher, reporter


def _write_and_edit(article: dict):
    """WriterAgentで執筆 → EditorAgent（編集長）レビューを通した最終稿を返す。

    Returns: 配信可能なコラムテキスト（差し戻し・生成失敗時は None）
    """
    column_text = writer.write(article)
    if not column_text:
        print(f"[Writer] 生成失敗（スキップ）: {article['title'][:40]}")
        return None

    e_passed, e_reason, revised = editor.review(article, column_text)
    if not e_passed:
        print(f"[Editor] 差し戻し: {article['title'][:40]} — {e_reason}")
        archive.archive_ng(article, e_reason, "editor", fixable=True)
        reporter.report_ng(article, e_reason, "editor", fixable=True)
        return None

    if revised:
        print(f"[Editor] 推敲修正あり — {article['title'][:40]}")
        return revised
    return column_text


def run_pipeline(is_irregular: bool = False) -> dict:
    """
    パイプライン1回分の実行。
    Returns: 実行サマリー dict
    """
    print(f"\n{'='*60}")
    print(f"[Pipeline] 開始 — {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
    if is_irregular:
        print("[Pipeline] モード：イレギュラー（主要ソース記事検知）")
    print('='*60)

    # ── Step 1: 収集 ───────────────────────────────────────
    articles, has_major = collector.collect()
    print(f"[Collector] 新規取得：{len(articles)}件 / 主要ソース検知：{has_major}")

    if not articles:
        print("[Pipeline] 配信対象記事なし → 管理者通知")
        reporter.report_no_articles()
        return {"status": "no_articles", "collected": 0}

    # ── Step 2〜4: Validator → Legal → Writer → Editor ─────
    passed_articles = []
    ng_count = 0

    for a in articles:
        # ValidatorAgent
        v_passed, v_reason = validator.validate(a)
        if not v_passed:
            print(f"[Validator] NG: {a['title'][:40]} — {v_reason}")
            fixable = "誇張" in v_reason or "表現" in v_reason
            archive.archive_ng(a, v_reason, "validator", fixable)
            reporter.report_ng(a, v_reason, "validator", fixable)
            ng_count += 1
            continue

        # LegalAgent
        l_passed, l_reason = legal.check(a)
        if not l_passed:
            print(f"[Legal] NG: {a['title'][:40]} — {l_reason}")
            archive.archive_ng(a, l_reason, "legal", fixable=False)
            reporter.report_ng(a, l_reason, "legal", fixable=False)
            ng_count += 1
            continue

        # WriterAgent → EditorAgent（編集長レビュー）
        column_text = _write_and_edit(a)
        if column_text:
            a["column_text"] = column_text
            passed_articles.append(a)
            print(f"[Writer/Editor] コラム確定 ✓ — {a['title'][:40]}")
        else:
            ng_count += 1

    # ── Step 5: NG率チェック ────────────────────────────────
    total = len(articles)
    passed = len(passed_articles)
    ng_rate = ng_count / total if total > 0 else 0

    print(f"[Pipeline] 通過：{passed}/{total}件 / NG率：{ng_rate:.0%}")

    if ng_rate > NG_RATE_THRESHOLD and passed == 0:
        print("[Pipeline] NG率超過 → 配信見送り")
        reporter.report_ng_rate_exceeded(total, passed, ng_rate)
        archive.mark_queued_as_archived()
        return {"status": "ng_rate_exceeded", "collected": total, "passed": passed}

    # ── Step 6: 再キュー記事を追加（修正可能なNG記事）──────
    retry_articles = archive.get_retry_queue()
    if retry_articles:
        print(f"[Archive] 再キュー記事追加：{len(retry_articles)}件")
        for ra in retry_articles:
            if not any(a["url"] == ra["url"] for a in passed_articles):
                col = _write_and_edit(ra)
                if col:
                    ra["column_text"] = col
                    passed_articles.append(ra)

    # ── Step 7: 配信 ────────────────────────────────────────
    if not passed_articles:
        print("[Pipeline] 配信記事なし → スキップ")
        reporter.report_no_articles()
        return {"status": "no_passed_articles", "collected": total}

    publisher.update_site(passed_articles)
    publisher.send_email(passed_articles, is_irregular=is_irregular)
    publisher.log_publish([id(a) for a in passed_articles], "both")

    archive.mark_queued_as_archived()

    print(f"[Pipeline] 完了 — {passed}件配信")
    print('='*60 + "\n")

    return {
        "status": "published",
        "collected": total,
        "passed": passed,
        "ng": ng_count,
    }


def start_scheduler():
    """APSchedulerで定期実行 + 2時間おきの収集"""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = BlockingScheduler(timezone="Asia/Tokyo")

    # 2時間おきの収集チェック（イレギュラー検知）
    def check_irregular():
        articles, has_major = collector.collect()
        if has_major and articles:
            print("[Scheduler] 主要ソース記事検知 → イレギュラー配信")
            run_pipeline(is_irregular=True)

    scheduler.add_job(
        check_irregular,
        IntervalTrigger(hours=2),
        id="collect_check",
        name="2時間おき収集チェック",
    )

    # 毎週月曜 08:30 定期配信
    scheduler.add_job(
        lambda: run_pipeline(is_irregular=False),
        CronTrigger(day_of_week=WEEKLY_DAY, hour=WEEKLY_HOUR, minute=WEEKLY_MINUTE),
        id="weekly_publish",
        name="週次定期配信（月曜08:30）",
    )

    print("[Scheduler] 起動")
    print(f"  - 収集チェック：2時間おき")
    print(f"  - 定期配信：毎週月曜 {WEEKLY_HOUR:02d}:{WEEKLY_MINUTE:02d}")
    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="St.NEA AIコラム配信パイプライン")
    parser.add_argument("--schedule", action="store_true", help="スケジューラモードで起動")
    args = parser.parse_args()

    init_db()

    if args.schedule:
        start_scheduler()
    else:
        result = run_pipeline()
        print(f"実行結果：{result}")
