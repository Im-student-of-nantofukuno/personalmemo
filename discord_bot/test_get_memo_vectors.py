
import os
import asyncio
from pathlib import Path

import aiohttp
from dotenv import load_dotenv


# .envを読み込む
load_dotenv(Path(__file__).with_name(".env"))

GAS_URL = os.getenv("GAS_URL")
GAS_API_SECRET = os.getenv("GAS_API_SECRET")


async def main():

    if not GAS_URL or not GAS_API_SECRET:
        print(".envの設定を確認してください。")
        return

    # GASへのリクエスト
    data = {
        "secret": GAS_API_SECRET,
        "action": "get_memo_vectors"
    }

    print("GASからEmbeddingを取得しています...")

    try:
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                GAS_URL,
                json=data
            ) as response:

                if response.status != 200:
                    print("HTTPエラー:", response.status)
                    return

                result = await response.json(
                    content_type=None
                )

        if not result.get("success"):
            print("GAS側でエラーが発生しました。")
            print("エラー種別:", result.get("error"))
            return

        vectors = result.get("results", [])

        print("\n========== 取得結果 ==========")
        print("取得成功")
        print("取得件数:", result.get("result_count"))

        # --------------------------------------
        # 取得データの検証
        # --------------------------------------

        valid_count = 0

        for item in vectors:

            embedding = item.get("embedding")

            if (
                isinstance(embedding, list)
                and len(embedding) == 768
                and all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    for value in embedding
                )
                and item.get("dimensions") == 768
                and item.get("model_id")
                    == "@cf/google/embeddinggemma-2"
                and isinstance(item.get("content"), str)
                and isinstance(item.get("memo_id"), str)
            ):
                valid_count += 1

        print("形式が正常な件数:", valid_count)

        if vectors:
            print("最初のEmbeddingの次元数:",
                  len(vectors[0].get("embedding", [])))

        if valid_count == len(vectors):
            print("\n検証成功！")
        else:
            print("\n一部のデータに問題があります。")

    except Exception as e:
        print("通信・処理エラー:", type(e).__name__)


if __name__ == "__main__":
    asyncio.run(main())
