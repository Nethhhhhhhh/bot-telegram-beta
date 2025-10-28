import os
import asyncio
import re
import logging
import sys
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError, SessionPasswordNeededError


# ========================
# CONFIGURATION
# ========================

API_ID = 29051835
API_HASH = "e38f841a01353479a7323fc713c61b32"

BOT_TOKEN = "8207251826:AAEILrQblxB2i7eLRX10GCUlBW2-pgz52Ak"  # Replace with your bot token

ADMIN_IDS = [1867350927]  # Your Telegram user ID(s)

DOWNLOAD_FOLDER = 'downloads'
BOT_SESSION_NAME = 'bot_session'
USER_SESSION_NAME = 'user_session'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========================
# BOT STATES
# ========================

user_states = {}
download_queue = {}

# ========================
# UTILITY FUNCTIONS
# ========================

def parse_telegram_link(link):
    """Parse a Telegram link to extract channel/chat reference and message ID."""
    private_pattern = r't\.me/c/(\d+)/(\d+)'
    private_match = re.search(private_pattern, link)
    
    if private_match:
        channel_id = int(private_match.group(1))
        message_id = int(private_match.group(2))
        return channel_id, message_id, True
    
    public_pattern = r't\.me/([^/]+)/(\d+)'
    public_match = re.search(public_pattern, link)
    
    if public_match:
        username = public_match.group(1)
        message_id = int(public_match.group(2))
        return username, message_id, False
    
    return None, None, None

def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

# ========================
# BOT INITIALIZATION
# ========================

bot = TelegramClient(BOT_SESSION_NAME, API_ID, API_HASH)
user_client = TelegramClient(USER_SESSION_NAME, API_ID, API_HASH)

# ========================
# BOT HANDLERS
# ========================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id

    buttons = [
        [Button.inline("📥 Download Single File", b"download_single")],
        [Button.inline("📥 Download Multiple Files", b"download_multiple")],
        [Button.inline("📋 My Downloads", b"my_downloads")],
        [Button.inline("ℹ️ Help", b"help")]
    ]

    welcome_message = (
        "🤖 **Telegram Media Downloader Bot**\n\n"
        "I can help you download media from Telegram channels, including:\n"
        "• Public channels\n"
        "• Private channels (you must be a member)\n"
        "• Restricted content\n\n"
        "Choose an option below to get started:"
    )

    await event.respond(welcome_message, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"download_single"))
async def download_single_callback(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_single_link"

    await event.edit(
        "📎 **Send me a Telegram link**\n\n"
        "Format examples:\n"
        "• `https://t.me/channelname/123`\n"
        "• `https://t.me/c/1234567890/456`\n\n"
        "Send /cancel to cancel."
    )

@bot.on(events.CallbackQuery(data=b"download_multiple"))
async def download_multiple_callback(event):
    user_id = event.sender_id
    user_states[user_id] = "waiting_multiple_links"
    download_queue[user_id] = []

    await event.edit(
        "📎 **Send me multiple Telegram links**\n\n"
        "Send each link in a separate message.\n"
        "When done, send /done to start downloading.\n"
        "Send /cancel to cancel.\n\n"
        f"Links added: 0"
    )

@bot.on(events.CallbackQuery(data=b"help"))
async def help_callback(event):
    help_text = (
        "📖 **How to use this bot:**\n\n"
        "1️⃣ **Single Download**: Send one Telegram link to download media\n\n"
        "2️⃣ **Multiple Downloads**: Send multiple links, then /done\n\n"
        "3️⃣ **Supported Links**:\n"
        "   • Public channels: `t.me/channelname/123`\n"
        "   • Private channels: `t.me/c/1234567890/456`\n\n"
        "⚠️ **Requirements**:\n"
        "   • You must be a member of private channels\n"
        "   • The account used for the bot must have access\n\n"
        "📌 **Commands**:\n"
        "   • /start - Main menu\n"
        "   • /cancel - Cancel current operation\n"
        "   • /done - Finish adding links (multi-download)\n"
        "   • /status - Check download status"
    )

    await event.edit(help_text)

@bot.on(events.NewMessage())
async def message_handler(event):
    if not event.text or not event.is_private:
        return

    user_id = event.sender_id
    text = event.text.strip()

    if text.startswith('/'):
        if text == '/cancel':
            user_states.pop(user_id, None)
            download_queue.pop(user_id, None)
            await event.respond("❌ Operation cancelled.",
                              buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]])
            return
        elif text == '/done' and user_id in download_queue:
            await process_download_queue(event, user_id)
            return
        elif text == '/status':
            await show_status(event, user_id)
            return
        elif text == '/start':
            user_states.pop(user_id, None)
            download_queue.pop(user_id, None)
            await start_handler(event)
            return

    state = user_states.get(user_id)

    if state == "waiting_single_link":
        await handle_single_link(event, user_id, text)
    elif state == "waiting_multiple_links":
        await handle_multiple_links(event, user_id, text)

async def handle_single_link(event, user_id, link):
    channel_ref, message_id, is_private = parse_telegram_link(link)

    if not channel_ref:
        await event.respond(
            "❌ Invalid link format. Please send a valid Telegram link.\n"
            "Example: `https://t.me/channelname/123`"
        )
        return

    user_states.pop(user_id, None)
    status_msg = await event.respond("🔄 Processing your request...")

    try:
        success = await download_media_for_user(user_client, link, user_id, status_msg)

        if success:
            await status_msg.edit(
                "✅ **Download Complete!**\n\nYour file has been downloaded successfully.",
                buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
            )
        else:
            await status_msg.edit(
                "❌ **Download Failed**\n\n"
                "Could not download the media. Make sure:\n"
                "• The link is valid\n"
                "• You're a member of the channel\n"
                "• The message still exists",
                buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
            )
    except Exception as e:
        logger.error(f"Download error for user {user_id}: {e}")
        await status_msg.edit(
            f"❌ **Error**: {str(e)}",
            buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
        )

async def handle_multiple_links(event, user_id, link):
    channel_ref, message_id, is_private = parse_telegram_link(link)

    if not channel_ref:
        await event.respond("⚠️ Invalid link format. Skipping this link.")
        return

    if user_id not in download_queue:
        download_queue[user_id] = []

    download_queue[user_id].append(link)
    count = len(download_queue[user_id])

    await event.respond(
        f"✅ Link added to queue\n📊 Total links: {count}\n\nSend more links or /done to start downloading."
    )

async def process_download_queue(event, user_id):
    if user_id not in download_queue or not download_queue[user_id]:
        await event.respond("❌ No links in queue.")
        return

    links = download_queue[user_id]
    total = len(links)

    user_states.pop(user_id, None)
    download_queue.pop(user_id, None)

    status_msg = await event.respond(
        f"🚀 Starting download of {total} files...\n⏳ This may take a while."
    )

    successful = 0
    failed = 0

    for i, link in enumerate(links, 1):
        try:
            await status_msg.edit(
                f"📥 Downloading {i}/{total}\n✅ Success: {successful}\n❌ Failed: {failed}"
            )

            success = await download_media_for_user(user_client, link, user_id, None)
            if success:
                successful += 1
            else:
                failed += 1

            await asyncio.sleep(2)

        except FloodWaitError as e:
            wait_time = e.seconds
            await status_msg.edit(f"⚠️ Flood wait: {wait_time}s — Pausing...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error in batch download: {e}")
            failed += 1

    await status_msg.edit(
        f"✅ **Batch Download Complete!**\n\n📊 Results:\n• Success: {successful}/{total}\n• Failed: {failed}/{total}",
        buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
    )

async def download_media_for_user(client, link, user_id, status_msg):
    try:
        if not client.is_connected():
            logger.info("User client disconnected. Reconnecting...")
            await client.start()
            logger.info("User client reconnected.")

        channel_ref, message_id, is_private = parse_telegram_link(link)
        if not channel_ref:
            logger.error(f"Failed to parse link: {link}")
            return False

        try:
            if is_private:
                entity = int(f"-100{channel_ref}")
            else:
                entity = await client.get_entity(channel_ref)
        except Exception as e:
            logger.error(f"Failed to resolve entity '{channel_ref}': {e}")
            return False

        try:
            message = await client.get_messages(entity, ids=message_id)
        except Exception as e:
            logger.error(f"Failed to fetch message {message_id} from {entity}: {e}")
            return False

        if not message or not message.media:
            logger.warning(f"No media found in message {message_id} from {entity}")
            return False

        user_folder = os.path.join(DOWNLOAD_FOLDER, str(user_id))
        os.makedirs(user_folder, exist_ok=True)

        if status_msg:
            await status_msg.edit("📥 Downloading media...")

        file_path = await client.download_media(message, file=user_folder)

        if not file_path or not os.path.exists(file_path):
            logger.error("Download returned invalid path or file does not exist.")
            return False

        file_size = os.path.getsize(file_path)

        if status_msg:
            await status_msg.edit("📤 Sending file to you...")

        await bot.send_file(
            user_id,
            file_path,
            caption=f"✅ Downloaded from: {link}\n📊 Size: {format_file_size(file_size)}",
            force_document=True
        )

        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {file_path}: {e}")

        return True

    except FloodWaitError as e:
        logger.warning(f"FloodWait triggered: waiting {e.seconds} seconds.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in download_media_for_user: {e}")
        return False

@bot.on(events.CallbackQuery(data=b"back_to_menu"))
async def back_to_menu(event):
    user_states.pop(event.sender_id, None)
    download_queue.pop(event.sender_id, None)
    await start_handler(event)

@bot.on(events.CallbackQuery(data=b"my_downloads"))
async def my_downloads_callback(event):
    await event.edit(
        "📋 **Download History**\n\nThis feature is coming soon!\nIt will show your recent downloads and statistics.",
        buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
    )

async def show_status(event, user_id):
    if user_id in download_queue and download_queue[user_id]:
        count = len(download_queue[user_id])
        await event.respond(f"📊 You have {count} links queued. Send /done to start.")
    else:
        await event.respond("✅ No active or pending downloads.")

# ========================
# ADMIN COMMANDS
# ========================

@bot.on(events.NewMessage(pattern='/admin'))
async def admin_panel(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ Access denied. You are not an admin.")
        return

    buttons = [
        [Button.inline("📊 Bot Statistics", b"admin_stats")],
        [Button.inline("👥 Active Users", b"admin_users")],
        [Button.inline("🔄 Restart Bot", b"admin_restart")],
        [Button.inline("📤 Broadcast (Soon)", b"disabled")]  # Placeholder
    ]

    await event.respond(
        "🔧 **Admin Panel**\n\nSelect an action:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"admin_stats"))
async def admin_stats_callback(event):
    if event.sender_id not in ADMIN_IDS:
        return

    stats = (
        "📊 **Bot Statistics**\n\n"
        f"• Active States: {len(user_states)}\n"
        f"• Queued Downloads: {len(download_queue)}\n"
        f"• User Client: {'🟢 Connected' if user_client.is_connected() else '🔴 Disconnected'}\n"
        f"• Bot Client: {'🟢 Running' if bot.is_connected() else '🔴 Stopped'}"
    )

    await event.edit(stats, buttons=[[Button.inline("🔙 Back", b"back_to_admin")]])

@bot.on(events.CallbackQuery(data=b"admin_users"))
async def admin_users_callback(event):
    if event.sender_id not in ADMIN_IDS:
        return

    if not user_states:
        await event.edit("👥 No active users.", buttons=[[Button.inline("🔙 Back", b"back_to_admin")]])
        return

    users_list = "👥 **Active Users (States):**\n\n"
    for uid, state in user_states.items():
        users_list += f"• `{uid}` → `{state}`\n"

    await event.edit(users_list, buttons=[[Button.inline("🔙 Back", b"back_to_admin")]])

@bot.on(events.CallbackQuery(data=b"admin_restart"))
async def admin_restart_callback(event):
    if event.sender_id not in ADMIN_IDS:
        return

    await event.edit("🔄 Restarting bot... Please wait 5-10 seconds.")
    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.on(events.CallbackQuery(data=b"back_to_admin"))
async def back_to_admin(event):
    if event.sender_id not in ADMIN_IDS:
        return
    await admin_panel(await event.get_message())

@bot.on(events.CallbackQuery(data=b"disabled"))
async def disabled_feature(event):
    await event.answer("🚧 Feature under development.", alert=True)

# ========================
# MAIN FUNCTION
# ========================

async def main():
    logger.info("🚀 Starting Telegram Downloader Bot...")

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    try:
        # Start bot client
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("✅ Bot client started.")

        # Start user client — handles interactive login & 2FA
        print("\n" + "="*50)
        print("📱 USER ACCOUNT LOGIN")
        print("="*50)
        print("If this is your first time running the bot,")
        print("you'll be prompted to log in to your Telegram account.")
        print("You may need to enter:")
        print("  • Phone number (with country code)")
        print("  • Login code (sent via Telegram)")
        print("  • 2FA password (if enabled)")
        print("="*50 + "\n")

        try:
            await user_client.start()
        except SessionPasswordNeededError:
            logger.warning("⚠️ Two-factor authentication is enabled. Enter your password when prompted.")
            await user_client.start()  # Will prompt for 2FA password

        if not await user_client.is_user_authorized():
            logger.critical("❌ User client authorization FAILED. Cannot download restricted content.")
            return

        me = await user_client.get_me()
        logger.info(f"✅ Logged in as user: {me.first_name} (@{me.username if me.username else 'No username'})")

        bot_me = await bot.get_me()
        logger.info(f"🤖 Bot running as: @{bot_me.username}")

        logger.info("🎉 Bot is ready and listening for commands!")
        await bot.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
    finally:
        if user_client.is_connected():
            await user_client.disconnect()
        if bot.is_connected():
            await bot.disconnect()
        logger.info("🔌 All clients disconnected. Goodbye!")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Process terminated by user.")
