import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import aiohttp
import asyncio

from test_cloudflare_ai import process_date_extraction
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

    await interaction.response.send_message(
        "質問を受け取りました。"
    )

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
                            "このメッセージは既に保存されています。"
                        )
                        print("既に保存済みのメッセージです。")

                    else:
                        await message.reply("メモを保存しました。")

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
