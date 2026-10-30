import re
import asyncio
import httpx
from telegram import ChatPermissions, Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TOKEN = "9243017774:AAF6jeABzNPBL3hQCJjZYqr-05NhYQlgq9U"
CHAT_ID = -1003938950393
X_AUTH_TOKEN = "0656aacdd9abc8c95a89f4c58a6870518da05fb0"
X_CT0 = "028acd745951e42d64f3bf8a58b1af32e4a95c0f80cd352d0e39f3e12b3772001348c377e7d52340b9a2766385c355828d94b702ee9ed94e50fe7f9239959232c763905e73edb4bc09c28bcefa6b4b9e"

pool_active = False
current_round_links = {}
TWITTER_REGEX = re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]+/status/(\d+)")

HEADERS = {
    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
    "x-csrf-token": X_CT0,
    "x-twitter-active-user": "yes",
    "x-twitter-auth-type": "OAuth2Session",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "content-type": "application/json"
}
COOKIES = {"auth_token": X_AUTH_TOKEN, "ct0": X_CT0}

async def x_action(tweet_id, action="rt"):
    query_id = "ojPdsDebugupqOONaoHUBrw" if action == "rt" else "iQtK4dl5h71VJ0qwmhSpLg"
    endpoint = "CreateRetweet" if action == "rt" else "DeleteRetweet"
    url = f"https://x.com/i/api/graphql/{query_id}/{endpoint}"
    payload = {"variables": {"tweet_id": tweet_id}, "queryId": query_id}
    async with httpx.AsyncClient(headers=HEADERS, cookies=COOKIES, timeout=15) as client:
        try:
            r = await client.post(url, json=payload)
            return r.status_code == 200
        except Exception:
            return False

async def process_cycle(tweet_ids):
    if not tweet_ids:
        return
    success_ids = []
    for tid in tweet_ids:
        if await x_action(tid, "rt"):
            success_ids.append(tid)
        await asyncio.sleep(3)

    await asyncio.sleep(900)

    for tid in success_ids:
        await x_action(tid, "unrt"):
        await asyncio.sleep(3)

async def open_pool(context: ContextTypes.DEFAULT_TYPE):
    global pool_active, current_round_links
    pool_active = True
    current_round_links = {}
    perms = ChatPermissions(can_send_messages=True)
    await context.bot.set_chat_permissions(chat_id=CHAT_ID, permissions=perms)
    msg = await context.bot.send_message(chat_id=CHAT_ID, text="?? **HAVUZ ACILDI (xx:30 - xx:35)**\n\nTweet linklerinizi paylasin. 35 gece kilitlenecektir!", parse_mode="Markdown")
    await context.bot.pin_chat_message(chat_id=CHAT_ID, message_id=msg.message_id)

async def close_pool(context: ContextTypes.DEFAULT_TYPE):
    global pool_active
    pool_active = False
    perms = ChatPermissions(can_send_messages=False)
    await context.bot.set_chat_permissions(chat_id=CHAT_ID, permissions=perms)
    total_links = sum(len(item["links"]) for item in current_round_links.values())
    await context.bot.send_message(chat_id=CHAT_ID, text=f"?? **HAVUZ KAPANDI (xx:35)**\n\nToplam {total_links} tweet toplandi.", parse_mode="Markdown")

async def publish_list(context: ContextTypes.DEFAULT_TYPE):
    tweet_ids = []
    all_links = []
    for user_data in current_round_links.values():
        tg_user = user_data["username"]
        total_user_links = len(user_data["links"])
        for idx, item in enumerate(user_data["links"], 1):
            all_links.append((item["x_account"], tg_user, item["url"], idx, total_user_links))
            tweet_ids.append(item["tweet_id"])
    if not all_links:
        return
    text = "?? **RT & BEGENI DALGASI BASLADI (xx:40)**\n\n"
    for i, (x_acc, tg_u, url, user_link_idx, total_u_links) in enumerate(all_links, 1):
        text += f"{i}. @{x_acc} gonderisi (Paylasan: {tg_u} - {user_link_idx}/{total_u_links})\n{url}\n\n"
    text += "?? *Not: RT'ler 15 dakika sonra otomatik geri cekilecektir.*"
    await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown", disable_web_page_preview=True)
    asyncio.create_task(process_cycle(tweet_ids))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pool_active
    if update.effective_chat.id != CHAT_ID or not pool_active:
        return
    text = update.message.text or ""
    match = TWITTER_REGEX.search(text)
    user = update.effective_user
    if match:
        tweet_id = match.group(1)
        tweet_link = match.group(0)
        x_account = tweet_link.split("/")[3]
        tg_name = f"@{user.username}" if user.username else user.first_name
        if user.id not in current_round_links:
            current_round_links[user.id] = {"username": tg_name, "links": []}
        user_links = current_round_links[user.id]["links"]
        if not any(item["tweet_id"] == tweet_id for item in user_links):
            user_links.append({"tweet_id": tweet_id, "x_account": x_account, "url": tweet_link})
    else:
        try:
            await update.message.delete()
        except Exception:
            pass

async def setup_jobs(app):
    jq = app.job_queue
    import datetime, pytz
    tz = pytz.timezone("Europe/Istanbul")
    for h in range(24):
        jq.run_daily(open_pool, time=datetime.time(hour=h, minute=30, tzinfo=tz))
        jq.run_daily(close_pool, time=datetime.time(hour=h, minute=35, tzinfo=tz))
        jq.run_daily(publish_list, time=datetime.time(hour=h, minute=40, tzinfo=tz))

def main():
    app = ApplicationBuilder().token(TOKEN).post_init(setup_jobs).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Sistem hazir, saat basi donguler devrede...")
    app.run_polling()

if __name__ == "__main__":
    main()
