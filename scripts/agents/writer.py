"""WriterAgent — コラム本文生成（サイト掲載 + メール配信用）"""

import anthropic

from scripts.config import ANTHROPIC_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


COLUMN_TEMPLATE = """あなたはSt.NEAのコンテンツライターエージェントです。
以下のAIニュースを、AIクリエイター・AIツール活用者向けのキャッチアップコラムとして日本語で書いてください。

タイトル：{title}
要約：{summary}
ソース：{source}
URL：{url}

出力フォーマット（必ずこの形式で）：

【タイトル】
（日本語タイトル・30〜40字）

📌 （要約1文・リード文、何がポイントかを端的に）

（コラム本文・200〜300字。何が変わったか、誰に関係するか、今日から使えるヒントを含める）

🔗 ソース：{url}

スタイルルール：
- 「革命的」「ヤバい」「完全自動化」は使わない
- 断言より「〜とみられます」「〜の可能性があります」
- 読んだ人がすぐ試せる内容を1つ含める
- 文末は「。」で統一

本文のみ出力してください。説明不要。"""


def write(article: dict):
    """
    Returns:
        コラムテキスト（失敗時 None）
    """
    prompt = COLUMN_TEMPLATE.format(
        title=article["title"],
        summary=article.get("summary", ""),
        source=article["source"],
        url=article["url"],
    )
    try:
        res = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return res.content[0].text.strip()
    except Exception as e:
        print(f"[Writer][WARN] {e}")
        return None
