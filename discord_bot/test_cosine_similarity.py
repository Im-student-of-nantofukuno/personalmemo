
import math


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


if __name__ == "__main__":
    a = [1, 0, 0]
    b = [1, 0, 0]
    c = [0, 1, 0]
    d = [-1, 0, 0]

    print("同じ方向:", cosine_similarity(a, b))
    print("直交する方向:", cosine_similarity(a, c))
    print("反対方向:", cosine_similarity(a, d))
