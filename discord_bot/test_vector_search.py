
import os
import asyncio
import math
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

from test_cloudflare_ai import (
    generate_embedding,
    generate_memo_answer
)

load_dotenv(Path(__file__).with_name(".env"))

GAS_URL = os.getenv("GAS_URL")
GAS_API_SECRET = os.getenv("GAS_API_SECRET")


def cosine_similarity(vector_a, vector_b):
    if len(vector_a) != len(vector_b):
        raise ValueError("ベクトルの次元数が一致しません。")

    dot_product = sum(
        a * b for a, b in zip(vector_a, vector_b)
    )

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        raise ValueError("ゼロベクトルは計算できません。")

    return dot_product / (norm_a * norm_b)


async def get_memo_vectors():
    data = {
        "secret": GAS_API_SECRET,
        "action": "get_memo_vectors"
    }

    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(GAS_URL, json=data) as response:

            if response.status != 200:
                print("HTTPエラー:", response.status)
                return None

            result = await response.json(content_type=None)

    if not result.get("success"):
        print("GAS側のエラー:", result.get("error"))
        return None

    return result.get("results", [])


async def main():

    if not GAS_URL or not GAS_API_SECRET:
        print(".envの設定を確認してください。")
        return

    # --------------------------------------
    # 1. 検索文章を入力
    # --------------------------------------

    query = input("検索したい文章を入力してください: ")

    if not query.strip():
        print("検索文章が空です。")
        return

    # --------------------------------------
    # 2. 検索文章をEmbeddingに変換
    # --------------------------------------

    print("\n検索文章をベクトル化しています...")

    query_embedding = generate_embedding(
        query,
        input_type="query"
    )

    if query_embedding is None:
        print("Embedding生成に失敗しました。")
        return

    # --------------------------------------
    # 3. GASから保存済みメモを取得
    # --------------------------------------

    print("保存済みメモを取得しています...")

    memos = await get_memo_vectors()

    if memos is None:
        return

    print("取得件数:", len(memos))

    # --------------------------------------
    # 4. 類似度を計算
    # --------------------------------------

    results = []

    for memo in memos:

        embedding = memo.get("embedding")

        if (
            not isinstance(embedding, list)
            or len(embedding) != 768
            or memo.get("dimensions") != 768
            or memo.get("model_id")
                != "@cf/google/embeddinggemma-2"
        ):
            continue

        try:
            score = cosine_similarity(
                query_embedding,
                embedding
            )

            results.append({
                "memo_id": memo["memo_id"],
                "content": memo["content"],
                "created_at": memo.get("created_at", ""),
                "score": score
            })

        except (ValueError, KeyError):
            continue

    # --------------------------------------
    # 5. 類似度の高い順に並べる
    # --------------------------------------

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # --------------------------------------
    # 6. 結果を表示
    # --------------------------------------

    print("\n========== 検索結果 ==========")

    if not results:
        print("検索できるメモがありません。")
        return

    for index, item in enumerate(results[:10], start=1):

        print(f"\n{index}位")
        print(f"類似度: {item['score']:.4f}")
        print(f"メモ: {item['content']}")

    print("\n検索完了！")

    # --------------------------------------
    # 7. 上位3件のメモを回答生成AIへ渡す
    # --------------------------------------

    selected_memos = [
        {
            "memo_id": item["memo_id"],
            "content": item["content"],
            "created_at": item["created_at"]
        }
        for item in results[:3]
    ]

    print("\n回答生成AIを実行しています...")

    answer_result = await asyncio.to_thread(
        generate_memo_answer,
        query,
        selected_memos
    )

    if answer_result is None:
        print("回答生成に失敗しました。")
        return

    print("\n========== AIの回答 ==========")

    print(answer_result["memo_answer"])

    if answer_result["general_knowledge"]:
        print("\n一般知識による補足:")
        print(answer_result["general_knowledge"])

    print("\n参照したメモID:")
    for memo_id in answer_result["used_memo_ids"]:
        print(memo_id)


if __name__ == "__main__":
    asyncio.run(main())
