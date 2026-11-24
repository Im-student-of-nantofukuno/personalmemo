
from test_cloudflare_ai import generate_embedding


def cosine_similarity(a, b):
    """2つのベクトルのコサイン類似度を計算する。"""

    dot = sum(x * y for x, y in zip(a, b))

    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0

    return dot / (norm_a * norm_b)


def main():
    memos = [
        "昨日は昼食に、おにぎりを2個食べた",
        "今日は数学の勉強をした",
        "先週、友達とゲームをした"
    ]

    question = "昨日の昼食に何を食べた？"

    # メモをベクトル化
    memo_embeddings = []

    for memo in memos:
        embedding = generate_embedding(memo, input_type="document")
        if embedding is None:
            print("メモのベクトル生成に失敗しました")
            return
        memo_embeddings.append(embedding)

    # 質問をベクトル化
    query_embedding = generate_embedding(
        question,
        input_type="query"
    )

    if query_embedding is None:
        print("質問のベクトル生成に失敗しました")
        return

    # 類似度を比較
    print(f"質問: {question}")
    print("\n========== 検索結果 ==========")

    results = []

    for memo, embedding in zip(memos, memo_embeddings):
        similarity = cosine_similarity(query_embedding, embedding)
        results.append((similarity, memo))

    results.sort(reverse=True)

    for similarity, memo in results:
        print(f"{similarity:.4f}: {memo}")


if __name__ == "__main__":
    main()
