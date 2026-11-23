
from datetime import datetime, timezone, timedelta
import dateparser

JST = timezone(timedelta(hours=9))
sent_at = datetime(2026, 11, 23, 8, 48, tzinfo=JST)

settings = {
    "RELATIVE_BASE": sent_at,
    "TIMEZONE": "Asia/Tokyo",
    "RETURN_AS_TIMEZONE_AWARE": True,
    "PREFER_DATES_FROM": "future",
    "STRICT_PARSING": False,
}

texts = [
    "3日後",
    "3日後に確認する",
    "来週の月曜日",
    "来週の月曜日に提出する",
    "来月",
    "12月5日に提出する",
]

for text in texts:
    result = dateparser.parse(
        text,
        languages=["ja"],
        settings=settings,
    )

    print(f"\n文章: {text}")
    print(f"parse: {result}")
