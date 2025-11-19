# main.py
# Telegram + GitHub Models AI bot (2025)
# Features: Emoji menu, animation, Khmer/English UI, admin panel, maintenance mode

import asyncio
import json
import logging
import os
from datetime import datetime
from functools import partial
from typing import Dict, List

# Azure/GitHub Models SDK
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

# Telegram SDK
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)

# -----------------------------
# CONFIG — FILL THESE VALUES
# -----------------------------
# ⚠️ REPLACE THESE WITH YOUR NEW TOKENS
TELEGRAM_BOT_TOKEN = "8537960594:AAG0GITpapJ0OQar7DWZDsTEYv-C45vhRpc"
GITHUB_TOKEN = "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" 
GITHUB_ENDPOINT = "https://models.github.ai/inference"
GITHUB_MODEL = "openai/gpt-4o" # Updated model name (gpt-4.1 is usually not a standard endpoint name, check available models)

# Admins who can edit bot (Telegram user IDs)
ADMIN_IDS = {1867350927}

# Animation GIF
ANIMATION_URL = "https://media.giphy.com/media/5k5vZwRFZR5aZeniqb/giphy.gif"

# Local storage
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------
# LOGGER
# -----------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tg-github-ai-bot")

# -----------------------------
# CONVERSATION STATES
# -----------------------------
# Define integer constants for conversation states
ADMIN_MENU, ADMIN_AWAIT_PROMPT, ADMIN_AWAIT_DONATION, ADMIN_AWAIT_BROADCAST = range(4)

# -----------------------------
# TRANSLATIONS
# -----------------------------
LANG_EN = "en"
LANG_KM = "km"

T = {
    LANG_EN: {
        "app_name": "AI Chat Assistant",
        "welcome_title": "👋 Welcome!",
        "welcome_body": "I’m your multilingual AI assistant powered by GitHub Models.\n\nChoose an option below or just start typing!",
        "menu_start": "🚀 Start",
        "menu_lang": "🌐 Language",
        "menu_help": "❓ Help",
        "menu_donate": "☕ Donate",
        "menu_support": "🛟 Support",
        "choose_language": "Choose your language:",
        "language_set_en": "Language set to English 🇺🇸",
        "language_set_km": "ប្ដូរភាសាទៅ ខ្មែរ 🇰🇭",
        "help_text": "Type any question and I’ll reply. Use the menu to switch language, get help, donate, or contact support.",
        "donate_text": "If you’d like to support the project, you can donate here:",
        "support_text": "Need help? Contact support:",
        "processing": "Thinking… 🤖",
        "maintenance": "🛠️ The bot is under maintenance. Please try again later.",
        "admin_nope": "You are not authorized to access admin tools.",
        "admin_title": "🛠️ Admin Panel",
        "admin_btn_prompt": "🧠 Edit System Prompt",
        "admin_btn_donation": "🔗 Set Donation Link",
        "admin_btn_broadcast": "📣 Broadcast Message",
        "admin_btn_maint_on": "🛑 Enable Maintenance",
        "admin_btn_maint_off": "✅ Disable Maintenance",
        "admin_btn_show_config": "📄 Show Config",
        "admin_btn_cancel": "✖️ Close",
        "admin_prompt_ask": "Send the new system prompt. This guides the AI’s behavior.",
        "admin_prompt_ok": "System prompt updated.",
        "admin_donation_ask": "Send the new donation link (e.g., BuyMeACoffee/Ko-fi/Your site).",
        "admin_donation_ok": "Donation link updated.",
        "admin_broadcast_ask": "Send the broadcast message (HTML allowed).",
        "admin_broadcast_ok": "Broadcast sent to {} users.",
        "admin_maint_on_ok": "Maintenance mode ENABLED.",
        "admin_maint_off_ok": "Maintenance mode DISABLED.",
        "chat_hint": "You can now send me a message to chat!",
    },
    LANG_KM: {
        "app_name": "អ្នកជំនួយការ AI",
        "welcome_title": "👋 សួស្តី!",
        "welcome_body": "ខ្ញុំជាជំនួយការ AI ពហុភាសា ដែលប្រើប្រាស់ GitHub Models។\n\nសូមជ្រើសរើសមួយខាងក្រោម ឬវាយសំណួររបស់អ្នក!",
        "menu_start": "🚀 ចាប់ផ្តើម",
        "menu_lang": "🌐 ភាសា",
        "menu_help": "❓ ជំនួយ",
        "menu_donate": "☕ គាំទ្រ",
        "menu_support": "🛟 ជំនួយបន្ទាន់",
        "choose_language": "សូមជ្រើសរើសភាសា៖",
        "language_set_en": "បានប្ដូរទៅភាសាអង់គ្លេស 🇺🇸",
        "language_set_km": "បានប្ដូរទៅភាសាខ្មែរ 🇰🇭",
        "help_text": "វាយសំណួរណាមួយ ខ្ញុំនឹងឆ្លើយតប។ ប្រើម៉ឺនុយ ដើម្បីប្ដូរភាសា ជំនួយ ឬគាំទ្រ។",
        "donate_text": "បើអ្នកចង់គាំទ្រគម្រោង សូមប្រើតំណខាងក្រោម៖",
        "support_text": "ត្រូវការជំនួយ? ទាក់ទងជំនួយបន្ទាន់៖",
        "processing": "កំពុងគិត… 🤖",
        "maintenance": "🛠️ បច្ចុប្បន្នកំពុងថែទាំ។ សូមព្យាយាមម្តងទៀត។",
        "admin_nope": "អ្នកមិនមានសិទ្ធិចូលប្រើឧបករណ៍អ្នកគ្រប់គ្រងទេ។",
        "admin_title": "🛠️ ផ្ទាំងអ្នកគ្រប់គ្រង",
        "admin_btn_prompt": "🧠 កែប្រែ System Prompt",
        "admin_btn_donation": "🔗 កំណត់តំណគាំទ្រ",
        "admin_btn_broadcast": "📣 ផ្ញើសារទៅអ្នកប្រើទាំងអស់",
        "admin_btn_maint_on": "🛑 បើកម៉ូដថែទាំ",
        "admin_btn_maint_off": "✅ បិទម៉ូដថែទាំ",
        "admin_btn_show_config": "📄 មើលការកំណត់",
        "admin_btn_cancel": "✖️ បិទ",
        "admin_prompt_ask": "សូមផ្ញើ System Prompt ថ្មី ដែលនាំផ្លូវឱ្យ AI។",
        "admin_prompt_ok": "បានធ្វើបច្ចុប្បន្នភាព System Prompt។",
        "admin_donation_ask": "សូមផ្ញើតំណគាំទ្រ (BuyMeACoffee/Ko-fi/គេហទំព័ររបស់អ្នក)។",
        "admin_donation_ok": "បានធ្វើបច្ចុប្បន្នភាពតំណគាំទ្រ។",
        "admin_broadcast_ask": "សូមផ្ញើសារផ្សព្វផ្សាយ (អនុញ្ញាត HTML)។",
        "admin_broadcast_ok": "បានផ្ញើសារទៅអ្នកប្រើ {} នាក់។",
        "admin_maint_on_ok": "បានបើកម៉ូដថែទាំ។",
        "admin_maint_off_ok": "បានបិទម៉ូដថែទាំ។",
        "chat_hint": "ឥឡូវនេះ អ្នកអាចផ្ញើសារដើម្បីជជែកជាមួយខ្ញុំបានហើយ!",
    },
}

# -----------------------------
# STORAGE
# -----------------------------
def load_json_file(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

USERS_DB = load_json_file(USERS_FILE, {"users": {}})
CONFIG = load_json_file(
    CONFIG_FILE,
    {
        "system_prompt": (
            "You are a friendly, bilingual AI assistant. "
            "Prefer replying in the user's chosen language (Khmer or English US). "
            "Be concise, helpful, and safe."
        ),
        "donation_link": "https://acledabank.com.kh/acleda?payment_data=qWY5B2SAUfIhLblxzOtfu5ckLzMHjaSki6Ru0bsOyNK+ylPBgZ0sHH6BeGUscKoE+dUiONasNDYwyZtGE5clSyncoVj6nqjYT/tbBSBxUOEGEFImM1x1Vs+SoaFhLb5y8MsJuFBp+yyzkC8Joe3O6RPYmT2lSbM1zCUMM5yA1q7uTYG6SHe+glJnuYVYR36t/nI1Zj39qo9cBu8TkjGpeQ==&key=khqr",
        "maintenance": False,
        "model": GITHUB_MODEL,
        "admins": list(ADMIN_IDS),
        "support_contact": "@your_support_handle",
    },
)

def save_users():
    save_json_file(USERS_FILE, USERS_DB)

def save_config():
    save_json_file(CONFIG_FILE, CONFIG)

def remember_user(user_id: int, lang: str):
    now = datetime.utcnow().isoformat()
    if str(user_id) not in USERS_DB["users"]:
        USERS_DB["users"][str(user_id)] = {"lang": lang, "created": now, "last": now}
    else:
        USERS_DB["users"][str(user_id)]["last"] = now
    save_users()

def get_user_lang(user_id: int) -> str:
    default_lang = LANG_EN
    user = USERS_DB["users"].get(str(user_id))
    if not user:
        return default_lang
    return user.get("lang", default_lang)

def set_user_lang(user_id: int, lang: str):
    if str(user_id) not in USERS_DB["users"]:
        remember_user(user_id, lang)
    USERS_DB["users"][str(user_id)]["lang"] = lang
    save_users()

# -----------------------------
# INLINE MENUS
# -----------------------------
def t(lang: str, key: str) -> str:
    return T.get(lang, T[LANG_EN]).get(key, key)

def main_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "menu_start"), callback_data="menu:start"),
            InlineKeyboardButton(t(lang, "menu_lang"), callback_data="menu:lang"),
        ],
        [
            InlineKeyboardButton(t(lang, "menu_help"), callback_data="menu:help"),
            InlineKeyboardButton(t(lang, "menu_donate"), callback_data="menu:donate"),
            InlineKeyboardButton(t(lang, "menu_support"), callback_data="menu:support"),
        ]
    ])

def language_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇸 English (US)", callback_data="lang:set:en"),
            InlineKeyboardButton("🇰🇭 ខ្មែរ", callback_data="lang:set:km"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:home")]
    ])

def admin_menu(lang: str) -> InlineKeyboardMarkup:
    m = []
    m.append([InlineKeyboardButton(t(lang, "admin_btn_prompt"), callback_data="admin:prompt")])
    m.append([InlineKeyboardButton(t(lang, "admin_btn_donation"), callback_data="admin:donation")])
    m.append([InlineKeyboardButton(t(lang, "admin_btn_broadcast"), callback_data="admin:broadcast")])
    if CONFIG.get("maintenance"):
        m.append([InlineKeyboardButton(t(lang, "admin_btn_maint_off"), callback_data="admin:maint_off")])
    else:
        m.append([InlineKeyboardButton(t(lang, "admin_btn_maint_on"), callback_data="admin:maint_on")])
    m.append([InlineKeyboardButton(t(lang, "admin_btn_show_config"), callback_data="admin:show")])
    m.append([InlineKeyboardButton(t(lang, "admin_btn_cancel"), callback_data="admin:cancel")])
    return InlineKeyboardMarkup(m)

# -----------------------------
# AI CLIENT (GitHub Models)
# -----------------------------
ai_client = None

def init_ai_client():
    global ai_client
    if not GITHUB_TOKEN or "GitHub" in GITHUB_TOKEN:
        logger.error("GitHub Token not set!")
        return
        
    ai_client = ChatCompletionsClient(
        endpoint=GITHUB_ENDPOINT,
        credential=AzureKeyCredential(GITHUB_TOKEN),
    )

async def call_model_async(messages: List[dict]) -> str:
    if not ai_client:
        return "System Error: AI Client not initialized (Check API Token)."
        
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(call_model_sync, messages))

def call_model_sync(messages: List[dict]) -> str:
    try:
        msg_objs = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                msg_objs.append(SystemMessage(content=content))
            else:
                msg_objs.append(UserMessage(content=content))
        
        result = ai_client.complete(
            model=CONFIG.get("model", GITHUB_MODEL),
            messages=msg_objs,
            temperature=0.4,
            max_tokens=800,
            top_p=0.9,
        )
        return result.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("AI call failed: %s", e)
        return "Sorry, I ran into an error talking to the AI model. Please try again."

# Session Storage
SESSIONS: Dict[int, List[dict]] = {}
MAX_TURNS = 12

def get_session(user_id: int) -> List[dict]:
    return SESSIONS.setdefault(user_id, [])

def add_to_session(user_id: int, role: str, content: str):
    sess = get_session(user_id)
    sess.append({"role": role, "content": content})
    if len(sess) > MAX_TURNS:
        del sess[0:len(sess) - MAX_TURNS]

# -----------------------------
# COMMAND HANDLERS
# -----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = get_user_lang(user_id) or LANG_EN
    remember_user(user_id, lang)

    if ANIMATION_URL:
        try:
            await update.effective_chat.send_animation(ANIMATION_URL, caption=None)
        except Exception as e:
            logger.warning("Failed to send animation: %s", e)

    text = f"<b>{t(lang, 'welcome_title')}</b>\n\n{t(lang, 'welcome_body')}"
    await update.effective_chat.send_message(
        text=text,
        reply_markup=main_menu(lang),
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update.effective_user.id)
    await update.effective_chat.send_message(
        text=f"ℹ️ <b>Help</b>\n\n{t(lang, 'help_text')}",
        parse_mode=ParseMode.HTML
    )

async def donate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update.effective_user.id)
    link = CONFIG.get("donation_link", "")
    await update.effective_chat.send_message(
        text=f"☕ <b>Donate</b>\n\n{t(lang, 'donate_text')}\n{link}",
        parse_mode=ParseMode.HTML
    )

async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update.effective_user.id)
    await update.effective_chat.send_message(
        text=t(lang, "choose_language"),
        reply_markup=language_menu(lang),
    )

async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update.effective_user.id)
    support = CONFIG.get("support_contact", "@your_support_handle")
    await update.effective_chat.send_message(
        text=f"🛟 <b>Support</b>\n\n{t(lang, 'support_text')} {support}",
        parse_mode=ParseMode.HTML
    )

# -----------------------------
# MENU CALLBACKS
# -----------------------------
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)

    data = query.data
    if data == "menu:home":
        await query.edit_message_text(
            text=f"<b>{t(lang, 'welcome_title')}</b>\n\n{t(lang, 'welcome_body')}",
            reply_markup=main_menu(lang),
            parse_mode=ParseMode.HTML
        )
    elif data == "menu:start":
        await query.edit_message_text(
            text=f"{t(lang, 'chat_hint')}",
            reply_markup=main_menu(lang),
        )
    elif data == "menu:lang":
        await query.edit_message_text(
            text=t(lang, "choose_language"),
            reply_markup=language_menu(lang),
        )
    elif data == "menu:help":
        await query.edit_message_text(
            text=f"ℹ️ <b>Help</b>\n\n{t(lang, 'help_text')}",
            reply_markup=main_menu(lang),
            parse_mode=ParseMode.HTML
        )
    elif data == "menu:donate":
        await query.edit_message_text(
            text=f"☕ <b>Donate</b>\n\n{t(lang, 'donate_text')}\n{CONFIG.get('donation_link','')}",
            reply_markup=main_menu(lang),
            parse_mode=ParseMode.HTML
        )
    elif data == "menu:support":
        await query.edit_message_text(
            text=f"🛟 <b>Support</b>\n\n{t(lang, 'support_text')} {CONFIG.get('support_contact','@your_support_handle')}",
            reply_markup=main_menu(lang),
            parse_mode=ParseMode.HTML
        )

async def lang_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "lang:set:en":
        set_user_lang(user_id, LANG_EN)
        msg = t(LANG_EN, "language_set_en")
    else:
        set_user_lang(user_id, LANG_KM)
        msg = t(LANG_KM, "language_set_km")

    lang = get_user_lang(user_id)
    await query.edit_message_text(
        text=f"{msg}",
        reply_markup=main_menu(lang)
    )

# -----------------------------
# ADMIN PANEL
# -----------------------------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    
    # Auth check
    if user_id not in ADMIN_IDS and str(user_id) not in map(str, CONFIG.get("admins", [])):
        await update.effective_chat.send_message(t(lang, "admin_nope"))
        return ConversationHandler.END

    await update.effective_chat.send_message(
        text=f"{t(lang, 'admin_title')}",
        reply_markup=admin_menu(lang),
    )
    return ADMIN_MENU

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)

    if user_id not in ADMIN_IDS and str(user_id) not in map(str, CONFIG.get("admins", [])):
        await query.edit_message_text(t(lang, "admin_nope"))
        return ConversationHandler.END

    data = query.data
    if data == "admin:prompt":
        await query.edit_message_text(t(lang, "admin_prompt_ask"))
        return ADMIN_AWAIT_PROMPT
    elif data == "admin:donation":
        await query.edit_message_text(t(lang, "admin_donation_ask"))
        return ADMIN_AWAIT_DONATION
    elif data == "admin:broadcast":
        await query.edit_message_text(t(lang, "admin_broadcast_ask"))
        return ADMIN_AWAIT_BROADCAST
    elif data == "admin:maint_on":
        CONFIG["maintenance"] = True
        save_config()
        await query.edit_message_text(
            f"{t(lang, 'admin_maint_on_ok')}",
            reply_markup=admin_menu(lang),
        )
        return ADMIN_MENU
    elif data == "admin:maint_off":
        CONFIG["maintenance"] = False
        save_config()
        await query.edit_message_text(
            f"{t(lang, 'admin_maint_off_ok')}",
            reply_markup=admin_menu(lang),
        )
        return ADMIN_MENU
    elif data == "admin:show":
        cfg = json.dumps(CONFIG, ensure_ascii=False, indent=2)
        await query.message.reply_text(f"<b>Config</b>\n<pre>{cfg}</pre>", parse_mode=ParseMode.HTML)
        return ADMIN_MENU
    elif data == "admin:cancel":
        await query.edit_message_text("✅ Closed.")
        return ConversationHandler.END

async def admin_set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    CONFIG["system_prompt"] = update.message.text.strip()
    save_config()
    await update.message.reply_text(t(lang, "admin_prompt_ok"), reply_markup=admin_menu(lang))
    return ADMIN_MENU

async def admin_set_donation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    CONFIG["donation_link"] = update.message.text.strip()
    save_config()
    await update.message.reply_text(t(lang, "admin_donation_ok"), reply_markup=admin_menu(lang))
    return ADMIN_MENU

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    text = update.message.text
    
    users = list(USERS_DB.get("users", {}).keys())
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=text, parse_mode=ParseMode.HTML)
            count += 1
        except Exception as e:
            logger.warning("Broadcast to %s failed: %s", uid, e)
    await update.message.reply_text(t(lang, "admin_broadcast_ok").format(count), reply_markup=admin_menu(lang))
    return ADMIN_MENU

async def admin_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ADMIN_MENU

# -----------------------------
# CHAT MESSAGE HANDLER
# -----------------------------
def build_system_message_for(user_lang: str) -> str:
    lang_instruction = "Reply in English (US)." if user_lang == LANG_EN else "Reply in Khmer."
    return f"{CONFIG.get('system_prompt')}\n\nUser language preference: {lang_instruction}"

def chunk_text(text: str, n: int = 3500):
    for i in range(0, len(text), n):
        yield text[i : i + n]

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = get_user_lang(user_id)

    if CONFIG.get("maintenance") and user_id not in ADMIN_IDS and str(user_id) not in map(str, CONFIG.get("admins", [])):
        await update.effective_chat.send_message(t(lang, "maintenance"))
        return

    remember_user(user_id, lang)
    user_text = update.message.text.strip()
    if not user_text:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    history = get_session(user_id)
    messages = [{"role": "system", "content": build_system_message_for(lang)}]
    for turn in history[-(MAX_TURNS - 2):]:
        messages.append(turn)
    messages.append({"role": "user", "content": user_text})

    placeholder = await update.effective_chat.send_message(t(lang, "processing"))

    reply = await call_model_async(messages)

    add_to_session(user_id, "user", user_text)
    add_to_session(user_id, "assistant", reply)

    try:
        chunks = list(chunk_text(reply))
        await placeholder.edit_text(chunks[0])
        for c in chunks[1:]:
            await update.effective_chat.send_message(c)
    except Exception:
        await update.effective_chat.send_message(reply)

# -----------------------------
# MAIN
# -----------------------------
async def post_init(app):
    cmds = [
        ("start", "Start the bot"),
        ("help", "Show help"),
        ("language", "Choose language"),
        ("donate", "Donate link"),
        ("support", "Contact support"),
        ("admin", "Admin panel"),
    ]
    await app.bot.set_my_commands(cmds)

def run():
    if not TELEGRAM_BOT_TOKEN or "YOUR_TELEGRAM" in TELEGRAM_BOT_TOKEN:
        logger.error("ERROR: Please set TELEGRAM_BOT_TOKEN in the script.")
        return

    init_ai_client()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Admin conversation
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_cmd)],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_callback, pattern=r"^admin:.+"),
            ],
            ADMIN_AWAIT_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_prompt)],
            ADMIN_AWAIT_DONATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_donation)],
            ADMIN_AWAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast)],
        },
        fallbacks=[MessageHandler(filters.ALL, admin_fallback)],
        name="admin_conv",
        persistent=False,
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("donate", donate_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("support", support_cmd))

    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:.+"))
    app.add_handler(CallbackQueryHandler(lang_set_callback, pattern=r"^lang:set:.+"))

    app.add_handler(admin_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    logger.info("Bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    run()