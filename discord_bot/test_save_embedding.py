
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

from test_cloudflare_ai import (
    generate_embedding,
    EMBEDDING_MODEL_ID,
    EMBEDDING_DIMENSIONS
)


# .envを読み込む
load_dotenv(Path(__file__).with_name(".env"))

GAS_URL = os.getenv("GAS_URL")
GAS_API_SECRET = os.getenv("GAS_API_SECRET")


def main():

    if not GAS_URL or not GAS_API_SECRET:
        print(".env の設定を確認してください。")
        return

    # ------------------------------------------
    # 1. テスト対象を指定
    # ------------------------------------------

    memo_id = input("保存先のmemo_idを入力してください: ").strip()
    content = input("対応するメモ本文を入力してください: ").strip()

    if not memo_id or not content:
        print("入力が空です。")
        return

    # ------------------------------------------
    # 2. Embeddingを生成
    # ------------------------------------------

    print("\nEmbeddingを生成しています...")

    embedding = generate_embedding(
        content,
        input_type="document"
    )

    if embedding is None:
        print("Embedding生成に失敗しました。")
        return

    print(f"生成成功: {len(embedding)}次元")

    # ------------------------------------------
    # 3. GASへ送信するデータを作成
    # ------------------------------------------

    request_data = {
        "secret": GAS_API_SECRET,
        "action": "save_embedding",
        "memo_id": memo_id,
        "embedding": embedding,
        "model_id": EMBEDDING_MODEL_ID,
        "dimensions": EMBEDDING_DIMENSIONS
    }

    data = json.dumps(request_data).encode("utf-8")

    request = Request(
        GAS_URL,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    # ------------------------------------------
    # 4. GASへ送信
    # ------------------------------------------

    print("GASへ送信しています...")

    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        if result.get("success"):
            print("\n保存成功！")
            print("保存状態:", result.get("status"))
            print("次元数:", result.get("dimensions"))
        else:
            print("\nGAS側でエラーが発生しました。")
            print("エラー種別:", result.get("error"))

    except HTTPError as e:
        print("HTTPエラー:", e.code)

    except URLError:
        print("通信エラーが発生しました。")

    except Exception as e:
        print("予期しないエラー:", type(e).__name__)


if __name__ == "__main__":
    main()
