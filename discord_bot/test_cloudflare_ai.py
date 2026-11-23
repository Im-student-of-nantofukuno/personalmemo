
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


# ==================================================
# 設定
# ==================================================

load_dotenv(Path(__file__).with_name(".env"))

ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

MODEL_ID = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

URL = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{ACCOUNT_ID}/ai/run/{MODEL_ID}"
)


# ==================================================
# 日付抽出用 JSON Schema
# ==================================================

DATE_SCHEMA = {
    "type": "object",
    "properties": {
        "date_mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": [
                            "plan",
                            "deadline",
                            "event",
                            "historical",
                            "other"
                        ]
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["date", "period"]
                    },
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "precision": {
                        "type": "string",
                        "enum": [
                            "day",
                            "month",
                            "year",
                            "period",
                            "unknown"
                        ]
                    },
                    "status": {
                        "type": "string",
                        "enum": [
                            "certain",
                            "approximate",
                            "ambiguous",
                            "unresolved"
                        ]
                    },
                    "note": {"type": "string"}
                },
                "required": [
                    "expression",
                    "role",
                    "kind",
                    "start_date",
                    "end_date",
                    "precision",
                    "status",
                    "note"
                ]
            }
        }
    },
    "required": ["date_mentions"]
}


# ==================================================
# AIへの指示
# ==================================================

SYSTEM_PROMPT = """
あなたは日本語の文章から日付表現を抽出するAIです。

次のルールを必ず守ってください。

1. 基準日時はユーザーが指定した日時です。
2. タイムゾーンは日本時間（JST）です。
3. 「明日」「3日後」などは基準日時から計算します。
4. 元の文章に存在する日付表現だけを抽出します。
5. 日付表現が複数ある場合はすべて抽出します。
6. 予定、期限、出来事、過去の出来事を区別します。
7. 曖昧な期間を無理に特定の日付に変換しません。
8. 判断できない場合は空文字列を使います。

statusの判定基準:
- certain: 基準日時と文章から日付を明確に特定できる
- approximate: おおよその日付や期間まで特定できる
- ambiguous: 複数の解釈が考えられる
- unresolved: 日付を解釈できない

9. expressionには元の文章にある表現をそのまま入れます。

10. 日付表現がない場合は空の配列を返します。

日付はYYYY-MM-DD形式で返してください。
月や年など、日まで特定できない場合は、
特定できない部分を無理に補完しないでください。
11. expressionには日付を表す部分だけを含め、
    その後に続く助詞（に、まで、から、など）は含めないでください。

12. roleの判定:
    - plan:
    予定している行動や実施日。
    例：「月曜日に提出する」「明日確認する」

    - deadline:
    明確な締切・期限。
    例：「月曜日までに提出しなければならない」
        「提出期限は月曜日」

    - event:
    試験、イベント、会議などの日程。
    例：「月曜日に試験がある」

    - historical:
    過去に起きた出来事。
    例：「昨日試験があった」

    - other:
    上記に当てはまらないもの。

    特に注意:
    「提出する」「確認する」「完成させる」などの動詞だけでは
    deadlineと判定してはいけません。
    「までに」などの期限を示す表現があるか確認してください。

13. 「提出する」「確認する」などの行動だけを理由に
    deadlineと判定してはいけません。

14. 「上旬」「中旬」「下旬」は期間として扱います。

    暫定的な期間の定義:
    - 上旬: 1日〜10日
    - 中旬: 11日〜20日
    - 下旬: 21日〜月末

15. 「来月中旬」のように期間が特定できる場合、
    kindはperiod、precisionはperiodとします。

16. 期間の開始日と終了日が計算できる場合は、
    start_dateとend_dateの両方を設定してください。

17. 期間の範囲が特定できる場合は、
    statusをapproximateとしてください。
    ambiguousは複数の解釈が考えられる場合に使います。
"""


# ==================================================
# AIへのリクエスト
# ==================================================


def extract_dates(text, message_datetime):
    """
    メッセージ本文と送信日時から日付情報を抽出する。

    Args:
        text (str): メッセージ本文
        message_datetime (datetime): Discordの送信日時

    Returns:
        dict | None: 抽出結果。失敗時はNone
    """

    # ----------------------------------------------
    # 1. 入力確認
    # ----------------------------------------------

    if not isinstance(text, str) or not text.strip():
        print("メッセージ本文が空です。")
        return None

    if not isinstance(message_datetime, datetime):
        print("送信日時はdatetime型で指定してください。")
        return None

    if message_datetime.tzinfo is None:
        print("送信日時にタイムゾーンが設定されていません。")
        return None

    if not ACCOUNT_ID or not API_TOKEN:
        print(".env の設定を確認してください。")
        return None

    # ----------------------------------------------
    # 2. 基準日時を日本時間に変換
    # ----------------------------------------------

    jst = ZoneInfo("Asia/Tokyo")

    base_datetime = message_datetime.astimezone(jst)

    base_datetime_text = base_datetime.strftime(
        "%Y-%m-%d %H:%M:%S JST"
    )

    # ----------------------------------------------
    # 3. AIへの入力を作成
    # ----------------------------------------------

    user_prompt = f"""
基準日時: {base_datetime_text}

抽出対象の文章:
{text}
"""

    request_body = {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": DATE_SCHEMA
        },
        "temperature": 0.1,
        "max_tokens": 1000
    }

    data = json.dumps(request_body).encode("utf-8")

    request = Request(
        URL,
        data=data,
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    # ----------------------------------------------
    # 4. Cloudflare Workers AIに送信
    # ----------------------------------------------

    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        if not result.get("success"):
            print("AIからエラーが返されました。")
            return None

        ai_response = result["result"]["response"]

        if not isinstance(ai_response, dict):
            print("AIの応答形式が不正です。")
            return None

        if not isinstance(
            ai_response.get("date_mentions"), list
        ):
            print("日付情報の形式が不正です。")
            return None

        return ai_response

    except HTTPError as e:
        print(f"HTTPエラー: {e.code}")
        print(e.read().decode("utf-8", errors="replace"))

    except URLError as e:
        print("通信エラーが発生しました。")
        print(e.reason)

    except (KeyError, ValueError, TypeError) as e:
        print(f"応答データの処理に失敗しました: {e}")

    except Exception as e:
        print(f"予期しないエラー: {type(e).__name__}")
        print(str(e))

    return None



def validate_date_result(result):
    """
    AIの日付抽出結果を検証する。

    正常ならTrue、異常があればFalseを返す。
    """

    from datetime import date

    # ----------------------------------------------
    # 1. 全体構造の確認
    # ----------------------------------------------

    if not isinstance(result, dict):
        print("エラー: 結果が辞書形式ではありません。")
        return False

    mentions = result.get("date_mentions")

    if not isinstance(mentions, list):
        print("エラー: date_mentionsが配列ではありません。")
        return False

    # ----------------------------------------------
    # 2. 各日付情報の確認
    # ----------------------------------------------

    required_keys = {
        "expression",
        "role",
        "kind",
        "start_date",
        "end_date",
        "precision",
        "status",
        "note"
    }

    allowed_roles = {
        "plan",
        "deadline",
        "event",
        "historical",
        "other"
    }

    allowed_kinds = {
        "date",
        "period"
    }

    allowed_precisions = {
        "day",
        "month",
        "year",
        "period",
        "unknown"
    }

    allowed_statuses = {
        "certain",
        "approximate",
        "ambiguous",
        "unresolved"
    }

    for index, item in enumerate(mentions):

        label = f"日付情報[{index}]"

        if not isinstance(item, dict):
            print(f"エラー: {label}が辞書形式ではありません。")
            return False

        if not required_keys.issubset(item.keys()):
            print(f"エラー: {label}に必須項目がありません。")
            return False

        # ------------------------------------------
        # 文字列項目の確認
        # ------------------------------------------

        string_keys = [
            "expression",
            "role",
            "kind",
            "start_date",
            "end_date",
            "precision",
            "status",
            "note"
        ]

        for key in string_keys:
            if not isinstance(item[key], str):
                print(f"エラー: {label}.{key}が文字列ではありません。")
                return False

        if not item["expression"].strip():
            print(f"エラー: {label}.expressionが空です。")
            return False

        # ------------------------------------------
        # 許可された値か確認
        # ------------------------------------------

        if item["role"] not in allowed_roles:
            print(f"エラー: {label}.roleが不正です。")
            return False

        if item["kind"] not in allowed_kinds:
            print(f"エラー: {label}.kindが不正です。")
            return False

        if item["precision"] not in allowed_precisions:
            print(f"エラー: {label}.precisionが不正です。")
            return False

        if item["status"] not in allowed_statuses:
            print(f"エラー: {label}.statusが不正です。")
            return False

        # ------------------------------------------
        # 日付の形式と実在確認
        # ------------------------------------------

        dates = {}

        for key in ["start_date", "end_date"]:

            value = item[key]

            if value == "":
                dates[key] = None
                continue

            try:
                parsed = date.fromisoformat(value)

                if parsed.isoformat() != value:
                    raise ValueError

                dates[key] = parsed

            except ValueError:
                print(f"エラー: {label}.{key}が不正な日付です。")
                return False

        start = dates["start_date"]
        end = dates["end_date"]

        # ------------------------------------------
        # 開始日と終了日の整合性
        # ------------------------------------------

        if start and end and start > end:
            print(f"エラー: {label}の開始日が終了日より後です。")
            return False

        if item["status"] in {"certain", "approximate"}:
            if start is None or end is None:
                print(f"エラー: {label}に必要な日付がありません。")
                return False

        if item["status"] in {"ambiguous", "unresolved"}:
            if item["precision"] == "unknown":
                if start is not None or end is not None:
                    print(f"エラー: {label}の精度と日付が矛盾しています。")
                    return False

        # ------------------------------------------
        # kindとprecisionの整合性
        # ------------------------------------------

        if item["kind"] == "date":
            if item["precision"] == "period":
                print(f"エラー: {label}のkindとprecisionが矛盾しています。")
                return False

        if item["kind"] == "period":
            if item["precision"] not in {"period", "unknown"}:
                print(f"エラー: {label}のkindとprecisionが矛盾しています。")
                return False

    return True

def process_date_extraction(text, message_datetime):
    """
    日付抽出から検証までを実行する。

    成功時：日付情報を返す
    失敗時：Noneを返す
    """

    result = extract_dates(text, message_datetime)

    if result is None:
        print("日付抽出失敗")
        return None

    if not validate_date_result(result):
        print("日付抽出失敗")
        return None

    return result["date_mentions"]

# ==================================================
# テスト実行
# ==================================================

def main():

    # Discordから受け取った日時を想定
    test_datetime = datetime(
        2026, 11, 23, 10, 20,
        tzinfo=ZoneInfo("Asia/Tokyo")
    )

    test_text = "3日後に確認する"

    result = extract_dates(
        test_text,
        test_datetime
    )

    print("\n========== AIの応答 ==========")

    if result is not None:

        if validate_date_result(result):
            print("検証成功！")
        else:
            print("検証失敗！")

        print(json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ))
    else:
        print("日付抽出に失敗しました。")

    # 検証関数の異常系テスト
    test_result = {
        "date_mentions": [
            {
                "expression": "3日後",
                "role": "plan",
                "kind": "date",
                "start_date": "2026-02-30",
                "end_date": "2026-02-30",
                "precision": "day",
                "status": "certain",
                "note": "テスト用の不正な日付"
            }
        ]
    }

    print("\n========== 検証テスト ==========")

    if validate_date_result(test_result):
        print("検証成功")
    else:
        print("不正なデータを検出しました")


if __name__ == "__main__":
    main()
