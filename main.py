import os
import asyncio
import re
import logging
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError, SessionPasswordNeededError


# ========================
# CONFIGURATION
# ========================

# Your existing API credentials (for downloading)
API_ID = 29051835
API_HASH = "e38f841a01353479a7323fc713c61b32"

# Bot token from BotFather - YOU MUST REPLACE THIS
BOT_TOKEN = "8207251826:AAEILrQblxB2i7eLRX10GCUlBW2-pgz52Ak"  # Get from @BotFather

# Admin user IDs (get your ID from @userinfobot)
ADMIN_IDS = [1867350927]  # Replace with your Telegram user ID

# Folders
DOWNLOAD_FOLDER = 'downloads'
BOT_SESSION_NAME = 'bot_session'

# Logging
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
    # Check for private channel format
    private_pattern = r't\.me/c/(\d+)/(\d+)'
    private_match = re.search(private_pattern, link)
    
    if private_match:
        channel_id = int(private_match.group(1))
        message_id = int(private_match.group(2))
        return channel_id, message_id, True
    
    # Check for public channel format
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

# Bot client (for interacting with users and downloading from accessible channels)
bot = TelegramClient(BOT_SESSION_NAME, API_ID, API_HASH)

# ========================
# BOT HANDLERS
# ========================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """Handle /start command."""
    user_id = event.sender_id
    
    buttons = [
        [Button.inline("📥 Download Single File", b"download_single")],
        [Button.inline("📥 Download Multiple Files", b"download_multiple")],
        [Button.inline("📋 My Downloads", b"my_downloads")],
        [Button.inline("ℹ️ Help", b"help")]
    ]
    
    welcome_message = (
        "🤖 **Telegram Media Downloader Bot**\n\n"
        "I can help you download media from Telegram channels where I'm a member:\n"
        "• Public channels\n"
        "• Private channels (if the bot is added)\n\n"
        "Choose an option below to get started:"
    )
    
    await event.respond(welcome_message, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"download_single"))
async def download_single_callback(event):
    """Handle single download request."""
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
    """Handle multiple download request."""
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
    """Show help message."""
    help_text = (
        "📖 **How to use this bot:**\n\n"
        "1️⃣ **Single Download**: Send one Telegram link to download media\n\n"
        "2️⃣ **Multiple Downloads**: Send multiple links, then /done\n\n"
        "3️⃣ **Supported Links**:\n"
        "   • Public channels: `t.me/channelname/123`\n"
        "   • Private channels: `t.me/c/1234567890/456`\n\n"
        "⚠️ **Requirements**:\n"
        "   • The bot must be a member of private channels\n"
        "   • The message must still exist\n\n"
        "📌 **Commands**:\n"
        "   • /start - Main menu\n"
        "   • /cancel - Cancel current operation\n"
        "   • /done - Finish adding links (multi-download)\n"
        "   • /status - Check download status"
    )
    
    await event.edit(help_text)

@bot.on(events.NewMessage())
async def message_handler(event):
    """Handle incoming messages based on user state."""
    # Ignore messages from channels/groups or without text
    if not event.text or not event.is_private:
        return
        
    user_id = event.sender_id
    text = event.text.strip()
    
    # Handle commands
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
            await start_handler(event)
            return
    
    # Check user state
    state = user_states.get(user_id)
    
    if state == "waiting_single_link":
        await handle_single_link(event, user_id, text)
    elif state == "waiting_multiple_links":
        await handle_multiple_links(event, user_id, text)

async def handle_single_link(event, user_id, link):
    """Process single link download."""
    channel_ref, message_id, is_private = parse_telegram_link(link)
    
    if not channel_ref:
        await event.respond(
            "❌ Invalid link format. Please send a valid Telegram link.\n"
            "Example: `https://t.me/channelname/123`"
        )
        return
    
    # Clear user state
    user_states.pop(user_id, None)
    
    # Send processing message
    status_msg = await event.respond("🔄 Processing your request...")
    
    try:
        # Download the media
        success = await download_media_for_user(
            bot,  # Use bot client instead of user_client
            link, 
            user_id, 
            status_msg
        )
        
        if success:
            await status_msg.edit(
                "✅ **Download Complete!**\n\n"
                "Your file has been downloaded successfully.",
                buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
            )
        else:
            await status_msg.edit(
                "❌ **Download Failed**\n\n"
                "Could not download the media. Make sure:\n"
                "• The link is valid\n"
                "• The bot has access to the channel\n"
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
    """Add link to download queue."""
    channel_ref, message_id, is_private = parse_telegram_link(link)
    
    if not channel_ref:
        await event.respond("⚠️ Invalid link format. Skipping this link.")
        return
    
    if user_id not in download_queue:
        download_queue[user_id] = []
    
    download_queue[user_id].append(link)
    count = len(download_queue[user_id])
    
    await event.respond(
        f"✅ Link added to queue\n"
        f"📊 Total links: {count}\n\n"
        f"Send more links or /done to start downloading."
    )

async def process_download_queue(event, user_id):
    """Process all links in user's download queue."""
    if user_id not in download_queue or not download_queue[user_id]:
        await event.respond("❌ No links in queue.")
        return
    
    links = download_queue[user_id]
    total = len(links)
    
    # Clear states
    user_states.pop(user_id, None)
    download_queue.pop(user_id, None)
    
    status_msg = await event.respond(
        f"🚀 Starting download of {total} files...\n"
        f"⏳ This may take a while."
    )
    
    successful = 0
    failed = 0
    
    for i, link in enumerate(links, 1):
        try:
            await status_msg.edit(
                f"📥 Downloading {i}/{total}\n"
                f"✅ Success: {successful}\n"
                f"❌ Failed: {failed}"
            )
            
            success = await download_media_for_user(
                bot,  # Use bot client instead of user_client
                link,
                user_id,
                None
            )
            
            if success:
                successful += 1
            else:
                failed += 1
                
            # Add delay to avoid flood
            await asyncio.sleep(2)
            
        except FloodWaitError as e:
            wait_time = e.seconds
            await status_msg.edit(
                f"⚠️ Flood wait: {wait_time}s\n"
                f"Pausing downloads..."
            )
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error in batch download: {e}")
            failed += 1
    
    await status_msg.edit(
        f"✅ **Batch Download Complete!**\n\n"
        f"📊 Results:\n"
        f"• Success: {successful}/{total}\n"
        f"• Failed: {failed}/{total}",
        buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
    )

async def download_media_for_user(client, link, user_id, status_msg):
    """Download media and send to user."""
    try:
        # Ensure bot client is connected
        if not client.is_connected():
            await client.start(bot_token=BOT_TOKEN)
            logger.info("Bot client started successfully")
        
        channel_ref, message_id, is_private = parse_telegram_link(link)
        
        if not channel_ref:
            logger.error(f"Failed to parse link: {link}")
            return False
        
        # Get the entity
        try:
            if is_private:
                full_channel_id = int(f"-100{channel_ref}")
                entity = full_channel_id
            else:
                entity = await client.get_entity(channel_ref)
        except Exception as e:
            logger.error(f"Failed to get entity: {e}")
            return False
        
        # Get the message
        try:
            message = await client.get_messages(entity, ids=message_id)
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            return False
        
        if not message or not message.media:
            logger.error("No media found in message")
            return False
        
        # Create user-specific download folder
        user_folder = os.path.join(DOWNLOAD_FOLDER, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        
        # Update status
        if status_msg:
            await status_msg.edit("📥 Starting download...")
        
        # Download the file
        file_path = await client.download_media(
            message,
            file=user_folder
        )
        
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            
            # Update status
            if status_msg:
                await status_msg.edit("📤 Sending file to you...")
            
            # Send the file
            await client.send_file(
                user_id,
                file_path,
                caption=f"✅ Downloaded from: {link}\n"
                       f"📊 Size: {format_file_size(file_size)}",
                force_document=True
            )
            
            # Clean up downloaded file
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not remove file {file_path}: {e}")
            
            return True
        else:
            logger.error("Download failed - no file path returned")
            return False
            
    except FloodWaitError as e:
        logger.error(f"Flood wait error: {e}")
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

@bot.on(events.CallbackQuery(data=b"back_to_menu"))
async def back_to_menu(event):
    """Return to main menu."""
    await start_handler(event)

@bot.on(events.CallbackQuery(data=b"my_downloads"))
async def my_downloads_callback(event):
    """Show user's download history (placeholder)."""
    await event.edit(
        "📋 **Download History**\n\n"
        "This feature is coming soon!\n"
        "It will show your recent downloads and statistics.",
        buttons=[[Button.inline("🏠 Back to Menu", b"back_to_menu")]]
    )

async def show_status(event, user_id):
    """Show current download status."""
    if user_id in download_queue:
        count = len(download_queue[user_id])
        await event.respond(f"📊 You have {count} links in queue.")
    else:
        await event.respond("✅ No active downloads.")

# ========================
# ADMIN COMMANDS
# ========================

@bot.on(events.NewMessage(pattern='/admin'))
async def admin_panel(event):
    """Admin panel for bot management."""
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ You are not authorized to use admin commands.")
        return
    
    buttons = [
        [Button.inline("📊 Bot Statistics", b"admin_stats")],
        [Button.inline("👥 User List", b"admin_users")],
        [Button.inline("🔄 Restart Bot", b"admin_restart")],
        [Button.inline("📤 Broadcast Message", b"admin_broadcast")]
    ]
    
    await event.respond(
        "🔧 **Admin Panel**\n\n"
        "Select an option:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"admin_stats"))
async def admin_stats_callback(event):
    """Show bot statistics."""
    if event.sender_id not in ADMIN_IDS:
        return
    
    stats = (
        "📊 **Bot Statistics**\n\n"
        f"• Active users: {len(user_states)}\n"
        f"• Download queues: {len(download_queue)}\n"
        f"• Bot client active: {bot.is_connected()}\n"
    )
    
    await event.edit(stats)

@bot.on(events.CallbackQuery(data=b"admin_users"))
async def admin_users_callback(event):
    """Show list of active users."""
    if event.sender_id not in ADMIN_IDS:
        return
    
    if not user_states:
        await event.edit("👥 No active users at the moment.")
        return
    
    users_list = "👥 **Active Users:**\n\n"
    for user_id, state in user_states.items():
        users_list += f"• User ID: `{user_id}` - State: {state}\n"
    
    await event.edit(users_list)

@bot.on(events.CallbackQuery(data=b"admin_restart"))
async def admin_restart_callback(event):
    """Restart the bot."""
    if event.sender_id not in ADMIN_IDS:
        return
    
    await event.edit("🔄 Restarting bot...")
    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.on(events.CallbackQuery(data=b"admin_broadcast"))
async def admin_broadcast_callback(event):
    """Broadcast message to all users."""
    if event.sender_id not in ADMIN_IDS:
        return
    
    await event.edit(
        "📤 **Broadcast Message**\n\n"
        "Send the message you want to broadcast to all users.",
        buttons=[[Button.inline("❌ Cancel", b"cancel_broadcast")]]
    )
    
    # Store broadcast mode
    user_states[event.sender_id] = "broadcasting"

@bot.on(events.CallbackQuery(data=b"cancel_broadcast"))
async def cancel_broadcast_callback(event):
    """Cancel broadcast."""
    if event.sender_id not in ADMIN_IDS:
        return
    
    user_states.pop(event.sender_id, None)
    await event.edit("❌ Broadcast cancelled.")

# ========================
# MAIN FUNCTION
# ========================

async def main():
    """Main bot function."""
    logger.info("Starting Telegram Downloader Bot...")
    
    # Create download folder if it doesn't exist
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    try:
        # Start the bot
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully")
        
        # Get bot info
        me = await bot.get_me()
        logger.info(f"Bot is running as @{me.username}")
        
        # Keep bot running
        logger.info("Bot is running...")
        await bot.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
    finally:
        # Disconnect bot
        await bot.disconnect()
        logger.info("Bot stopped")

if __name__ == '__main__':
    import sys
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
