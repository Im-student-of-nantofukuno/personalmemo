import discord
from dotenv import load_dotenv
import os
import aiohttp

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
client = discord.Client(intents=intents)


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

                else:
                    print("GAS側でエラーが発生しました。")
                    print(f"HTTPステータス: {response.status}")
                    print(f"エラー種別: {result.get('error')}")

    except Exception as error:
        print("--------------------------------")
        print("GASへの送信に失敗しました。")
        print(f"エラー種別: {type(error).__name__}")
        print("--------------------------------")


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

    # GASへ保存
    await save_to_gas(message)


client.run(TOKEN)
