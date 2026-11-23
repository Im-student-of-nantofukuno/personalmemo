
import os
import asyncio
from datetime import datetime
import aiohttp
from dotenv import load_dotenv

# .envから設定を読み込む
load_dotenv()

GAS_URL = os.getenv("GAS_URL")
GAS_API_SECRET = os.getenv("GAS_API_SECRET")


async def main():

    if not GAS_URL or not GAS_API_SECRET:
        print("GAS_URL または GAS_API_SECRET が設定されていません。")
        return

    # テスト用データ
    data = {
        "secret": GAS_API_SECRET,
        "action": "save_memo",
        "content": "PythonからのGAS接続テスト",
        "discord_message_id": (
            "python_test_" + datetime.now().strftime("%Y%m%d%H%M%S")
        ),
        "source_user_id": "python_connection_test",
        "created_at": datetime.now().astimezone().isoformat()
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GAS_URL, json=data) as response:

                result = await response.json(content_type=None)

                print(f"HTTPステータス: {response.status}")
                print(f"GASの処理結果: {result.get('success')}")

                if result.get("success"):
                    print("GASへの保存に成功しました。")
                    print(f"メモID: {result.get('memo_id')}")
                    print(f"重複判定: {result.get('duplicated')}")
                else:
                    print("GAS側でエラーが発生しました。")
                    print(f"エラー種別: {result.get('error')}")

    except Exception as error:
        print("GASへの接続に失敗しました。")
        print(f"エラー種別: {type(error).__name__}")


asyncio.run(main())
