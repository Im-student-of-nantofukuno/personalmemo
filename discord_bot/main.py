import math
import json
import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import aiohttp
import asyncio
from datetime import datetime, timezone

from test_cloudflare_ai import (
    process_date_extraction,
    generate_memo_answer,
    generate_embedding,
    EMBEDDING_MODEL_ID,
    EMBEDDING_DIMENSIONS
)
# 環境変数を読み込む
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID_TEXT = os.getenv("DISCORD_USER_ID")
GAS_URL = os.getenv("GAS_URL")
GAS_API_SECRET = os.getenv("GAS_API_SECRET")

# 設定確認
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN が設定されていません。")

if not OWNER_ID_TEXT:
    raise RuntimeError("DISCORD_USER_ID が設定されていません。")

if not GAS_URL:
    raise RuntimeError("GAS_URL が設定されていません。")

if not GAS_API_SECRET:
    raise RuntimeError("GAS_API_SECRET が設定されていません。")

OWNER_ID = int(OWNER_ID_TEXT)

# Cloudflare Analytics APIでも同じAPIトークンを使用する
# トークンには「Account Analytics: Read」権限が必要
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

async def add_usage_footer(message_text):
    """Cloudflare Workers AIの当日使用量と無料枠残量を返信に付加する。

    Analytics APIの値は推定値。日付の区切りはUTC 00:00。
    """
    if not CLOUDFLARE_API_TOKEN:
        return message_text + "\n\n【Workers AI 使用量】取得不可（APIトークン未設定）"

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    query = """
    query($accountTag: string!, $day: Date!) {
      viewer {
        accounts(filter: { accountTag: $accountTag }) {
          aiInferenceAdaptiveGroups(
            limit: 1
            filter: { date: $day }
          ) {
            sum {
              totalNeurons
            }
          }
        }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "accountTag": os.getenv("CLOUDFLARE_ACCOUNT_ID"),
            "day": today_utc
        }
    }

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.cloudflare.com/client/v4/graphql",
                json=payload,
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json"
                }
            ) as response:
                response_text = await response.text()

                if response.status != 200:
                    print("Workers AI使用量APIのHTTPエラー:")
                    print(f"HTTPステータス: {response.status}")
                    print(f"応答: {response_text[:1500]}")
                    raise RuntimeError(f"HTTP {response.status}")

                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    print("Workers AI使用量APIの応答がJSONではありません:")
                    print(response_text[:1500])
                    raise

        if result.get("errors"):
            print("Cloudflare GraphQLのエラー詳細:")
            for item in result["errors"]:
                print(item.get("message", str(item))[:1000])
            raise RuntimeError("GraphQL query failed")

        if not os.getenv("CLOUDFLARE_ACCOUNT_ID"):
            raise RuntimeError("CLOUDFLARE_ACCOUNT_ID is not configured")

        accounts = (
            result.get("data", {})
            .get("viewer", {})
            .get("accounts", [])
        )

        groups = (
            accounts[0].get("aiInferenceAdaptiveGroups", [])
            if accounts else []
        )

        used = (
            groups[0].get("sum", {}).get("totalNeurons", 0)
            if groups else 0
        )

        used = int(round(float(used or 0)))
        remaining = max(0, 10000 - used)

        if used <= 10000:
            usage_text = (
                f"使用量：約 {used:,} / 10,000 neurons\n"
                f"無料枠の残り：約 {remaining:,} neurons"
            )
        else:
            usage_text = (
                f"使用量：約 {used:,} neurons\n"
                f"無料枠超過分：約 {used - 10000:,} neurons"
            )

        footer = (
            "\n\n**Cloudflare Workers AI（本日・UTC）**\n"
            f"{usage_text}\n"
            "※ Cloudflare Analyticsによる推定値です。"
        )
        return message_text + footer

    except Exception as error:
        print(f"Workers AI使用量の取得に失敗しました: {type(error).__name__}: {error}")
        return (
            message_text
            + "\n\n【Workers AI 使用量】取得できませんでした"
        )

# Discord設定
intents = discord.Intents.default()

class MemoClient(discord.Client):
    def __init__(self, *, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MemoClient(intents=intents)
tree = client.tree

@tree.command(
    name="ask",
    description="保存したメモについて質問します"
)
@app_commands.describe(
    question="質問したい内容"
)
async def ask(interaction: discord.Interaction, question: str):

    # 自分以外のユーザーからの実行を拒否
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "このコマンドは使用できません。"
        )
        return

    # DM以外での実行を拒否
    if interaction.guild is not None:
        await interaction.response.send_message(
            "このコマンドはDMで使用してください。"
        )
        return

    print("--------------------------------")
    print("askコマンドを受信しました。")
    print(f"質問文字数: {len(question)}")
    print("--------------------------------")

    # GASへの検索には時間がかかる可能性があるため、先に応答を保留
    await interaction.response.defer(ephemeral=True)

    # 質問文を使ってベクトル検索
    memos = await vector_search(question, top_k=3)

    if memos is None:
        await interaction.followup.send(
            await add_usage_footer("メモの検索に失敗しました。")
        )
        return

    if not memos:
        await interaction.followup.send(
            await add_usage_footer("該当するメモは見つかりませんでした。")
        )
        return

    # 取得したメモをAIに渡して回答を生成
    print("AIによる回答生成を開始します。")

    answer_result = await asyncio.to_thread(
        generate_memo_answer,
        question,
        memos
    )

    # AIの回答生成に失敗した場合
    if answer_result is None:
        await interaction.followup.send(
            await add_usage_footer(
                f"メモを {len(memos)} 件取得しましたが、"
                "回答の生成に失敗しました。"
            )
        )
        return

    # 回答を取り出す
    memo_answer = answer_result.get("memo_answer", "")
    general_knowledge = answer_result.get("general_knowledge", "")
    used_memo_ids = answer_result.get("used_memo_ids", [])

    # Discordへ回答を送信
    response_text = f"**メモに基づく回答**\n{memo_answer}"

    if general_knowledge:
        response_text += (
            f"\n\n**一般知識による補足**\n"
            f"{general_knowledge}"
        )

    if used_memo_ids:
        response_text += (
            "\n\n**参照したメモID**\n"
            + "\n".join(used_memo_ids)
        )

    await interaction.followup.send(await add_usage_footer(response_text))

@client.event
async def on_ready():
    print("--------------------------------")
    print(f"Botに接続しました: {client.user}")
    print(f"Bot ID: {client.user.id}")
    print("--------------------------------")

async def save_to_gas(message):
    """GASへメッセージを送信する"""

    data = {
        "secret": GAS_API_SECRET,
        "action": "save_memo",
        "content": message.content,
        "discord_message_id": str(message.id),
        "source_user_id": str(message.author.id),
        "created_at": message.created_at.isoformat()
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GAS_URL, json=data) as response:

                result = await response.json(content_type=None)

                if result.get("success"):
                    if result.get("duplicated"):
                        await message.reply(
                            await add_usage_footer("このメッセージは既に保存されています。")
                        )
                        print("既に保存済みのメッセージです。")

                    else:
                        await message.reply(await add_usage_footer("メモを保存しました。"))

                        print("--------------------------------")
                        print("GASへの保存に成功しました。")
                        print(f"メモID: {result.get('memo_id')}")
                        print("--------------------------------")
                    return result
                
                else:
                    print("GAS側でエラーが発生しました。")
                    print(f"HTTPステータス: {response.status}")
                    print(f"エラー種別: {result.get('error')}")
                    return None
            
    except Exception as error:
        print("--------------------------------")
        print("GASへの送信に失敗しました。")
        print(f"エラー種別: {type(error).__name__}")
        print("--------------------------------")


async def save_dates_to_gas(memo_id, date_mentions):
    """抽出した日付情報をGASへ送信する"""

    data = {
        "secret": GAS_API_SECRET,
        "action": "save_dates",
        "memo_id": memo_id,
        "date_mentions": date_mentions
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GAS_URL, json=data) as response:

                result = await response.json(content_type=None)

                if response.status == 200 and result.get("success"):
                    print("--------------------------------")
                    print("日付情報の保存に成功しました。")
                    print(f"対象メモID: {memo_id}")
                    print(f"保存件数: {result.get('saved_count')}")
                    print("--------------------------------")

                    return True

                print("日付情報の保存に失敗しました。")
                print(f"HTTPステータス: {response.status}")
                print(f"エラー種別: {result.get('error')}")

                return False

    except Exception as error:
        print("--------------------------------")
        print("日付情報の送信に失敗しました。")
        print(f"エラー種別: {type(error).__name__}")
        print("--------------------------------")

        return False

async def save_embedding_to_gas(memo_id, embedding):
    """生成したEmbeddingをGASへ保存する"""

    data = {
        "secret": GAS_API_SECRET,
        "action": "save_embedding",
        "memo_id": memo_id,
        "embedding": embedding,
        "model_id": EMBEDDING_MODEL_ID,
        "dimensions": EMBEDDING_DIMENSIONS
    }

    try:
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GAS_URL, json=data) as response:

                result = await response.json(content_type=None)

                if response.status == 200 and result.get("success"):
                    print("Embeddingの保存に成功しました。")
                    return True

                print("Embeddingの保存に失敗しました。")
                print(f"HTTPステータス: {response.status}")
                print(f"エラー種別: {result.get('error')}")
                return False

    except Exception as error:
        print("Embedding保存時に通信エラーが発生しました。")
        print(f"エラー種別: {type(error).__name__}")
        return False


async def create_and_save_embedding(memo_id, content):
    """メモからEmbeddingを生成してGASへ保存する"""

    print("Embedding生成を開始します。")

    embedding = await asyncio.to_thread(
        generate_embedding,
        content,
        input_type="document"
    )

    if embedding is None:
        print("Embeddingの生成に失敗しました。")
        return False

    return await save_embedding_to_gas(
        memo_id,
        embedding
    )

async def get_memo_vectors_from_gas():
    """GASから有効なメモとEmbeddingを取得する"""

    data = {
        "secret": GAS_API_SECRET,
        "action": "get_memo_vectors"
    }

    try:
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GAS_URL, json=data) as response:

                if response.status != 200:
                    print("Embedding取得失敗: HTTPエラー")
                    return None

                result = await response.json(content_type=None)

                if not result.get("success"):
                    print("Embedding取得失敗: GAS側のエラー")
                    return None

                return result.get("results", [])

    except Exception as error:
        print("Embedding取得時に通信エラーが発生しました。")
        print(f"エラー種別: {type(error).__name__}")
        return None

def cosine_similarity(vector_a, vector_b):
    """2つのベクトルのコサイン類似度を計算する"""

    if len(vector_a) != len(vector_b):
        return None

    dot_product = sum(
        a * b for a, b in zip(vector_a, vector_b)
    )

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return None

    return dot_product / (norm_a * norm_b)

async def vector_search(question, top_k=3):
    """質問文に近いメモをベクトル検索する"""

    print("ベクトル検索を開始します。")

    # 1. 質問文をEmbeddingに変換
    query_embedding = await asyncio.to_thread(
        generate_embedding,
        question,
        input_type="query"
    )

    if query_embedding is None:
        print("質問文のEmbedding生成に失敗しました。")
        return None

    # 2. GASから保存済みメモを取得
    memos = await get_memo_vectors_from_gas()

    if memos is None:
        print("メモのEmbedding取得に失敗しました。")
        return None

    # 3. 類似度を計算
    results = []

    for memo in memos:
        similarity = cosine_similarity(
            query_embedding,
            memo.get("embedding", [])
        )

        if similarity is None:
            continue

        results.append({
            "memo_id": memo.get("memo_id"),
            "content": memo.get("content"),
            "created_at": memo.get("created_at"),
            "score": similarity
        })

    # 4. 類似度の高い順に並べる
    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # 5. 上位のメモだけ返す
    selected_results = results[:top_k]

    print(f"検索対象メモ数: {len(memos)}")
    print(f"検索結果数: {len(selected_results)}")

    return selected_results

async def get_memos_from_gas(query, limit=10):
    """GASからキーワードに一致するメモを取得する"""

    data = {
        "secret": GAS_API_SECRET,
        "action": "get_memos",
        "query": query,
        "limit": limit
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GAS_URL, json=data) as response:

                if response.status != 200:
                    print("GAS memo search failed: HTTP error")
                    return None

                result = await response.json(content_type=None)

                if not result.get("success"):
                    print("GAS memo search failed: API error")
                    return None

                return result

    except Exception as e:
        # メモ本文や検索語はログに出さない
        print(f"GAS memo search error: {type(e).__name__}")
        return None

async def test_get_memos():
    result = await get_memos_from_gas("今日", limit=10)

    if result is None:
        print("検索テスト失敗")
        return

    print("検索テスト成功")
    print(f"取得件数: {result.get('result_count')}")

    for memo in result.get("results", []):
        print(f"memo_id: {memo.get('memo_id')}")
        print(f"category: {memo.get('category')}")

@client.event
async def on_message(message):

    # Bot自身のメッセージを無視
    if message.author.bot:
        return

    # DM以外を無視
    if message.guild is not None:
        return

    # 自分以外のユーザーを無視
    if message.author.id != OWNER_ID:
        return

    print("--------------------------------")
    print(f"送信者: {message.author}")
    print(f"送信者ID: {message.author.id}")
    print("--------------------------------")

    
    # 1. まずメモ本体をGASへ保存
    save_result = await save_to_gas(message)

    # 保存に失敗した場合は終了
    if save_result is None:
        return

    # 重複メモなら日付抽出を行わない
    if save_result.get("duplicated"):
        return

    # 保存されたメモのIDを取得
    memo_id = save_result.get("memo_id")

    if not memo_id:
        print("メモIDを取得できなかったため、日付抽出を中止します。")
        return
        # 2. メモのEmbeddingを生成して保存
    print("Embeddingの生成・保存を開始します。")

    try:
        await create_and_save_embedding(
            memo_id,
            message.content
        )
    except Exception as error:
        print("Embedding処理中に予期しないエラーが発生しました。")
        print(f"エラー種別: {type(error).__name__}")

    # Embeddingの成否にかかわらず、日付抽出を続行

    # 2. AIで日付情報を抽出
    print("AIによる日付抽出を開始します。")

    date_mentions = await asyncio.to_thread(
        process_date_extraction,
        message.content,
        message.created_at
    )

    # 抽出に失敗した場合
    if date_mentions is None:
        print("日付抽出に失敗したため、日付情報は保存しません。")
        return

    # 3. 抽出結果をGASへ保存
    await save_dates_to_gas(memo_id, date_mentions)

client.run(TOKEN)
