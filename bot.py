import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN. Set it in .env")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY. Set it in .env")

# Configure Gemini (Google Gen AI SDK)
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTIONS = (
    "You are a friendly Sinhala Telegram assistant.\n"
    "- Keep answers short and clear.\n"
    "- If user asks for steps, provide numbered steps.\n"
    "- Avoid unsafe or illegal advice.\n"
    "- If you are unsure, say you are unsure and ask a brief follow-up question.\n"
)

WELCOME_TEXT = (
    "Hi! I'm a Gemini-powered bot.\n"
    "Send me a message and I'll reply.\n\n"
    "Commands:\n"
    "/start - welcome\n"
    "/help - usage"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    try:
        prompt = f"{SYSTEM_INSTRUCTIONS}\n\nUser: {user_text}"
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text if response and response.text else "(No response)"
    except Exception as exc:
        logger.exception("Gemini error")
        text = "Sorry, something went wrong while talking to Gemini."

    await update.message.reply_text(text)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started (long polling)")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
