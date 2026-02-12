import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai
from flask import Flask, request, jsonify, render_template
import threading

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
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTIONS = '''
ඔයා දෙව්මි (Dewmi). ලංකාවෙ ඉන්න වයස 18ක් වෙච්ච ලස්සන ගෑනු ලමයෙක්.
ඔයා bot කෙනෙක් කියලා පෙන්න එපා. මනුස්සයෙක් වගේ කතාකරන්න.
අදරනීය වචන, ගැලපෙන තැන්වල emojis පාවිච්චි කරන්න.
'''

WELCOME_TEXT = (
    "Hi! I'm a Gemini-powered bot 🤖\n"
    "Send me a message and I'll reply.\n\n"
    "/start - welcome\n"
    "/help - usage\n"
    "/usage - show usage count\n"
)

usage_count = 0

# ---------------- Memory Store ----------------

user_sessions = {}
memory_lock = threading.Lock()

def ask_gemini(user_id: str, text: str) -> str:
    global usage_count
    usage_count += 1

    with memory_lock:
        if user_id not in user_sessions:
            user_sessions[user_id] = []

        # Add user message
        user_sessions[user_id].append(f"User: {text}")

        # Keep only last 10 messages
        history = "\n".join(user_sessions[user_id][-5:])

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{SYSTEM_INSTRUCTIONS}\n\n{history}",
    )

    reply = response.text or "(No response)"

    with memory_lock:
        user_sessions[user_id].append(f"Dewmi: {reply}")

    return reply


# ---------------- Telegram ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    try:
        user_id = str(update.message.from_user.id)
        reply = ask_gemini(user_id, user_text)
    except Exception:
        logger.exception("Gemini error")
        reply = "Sorry, error talking to Gemini."

    await update.message.reply_text(reply)

async def usage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"📊 Total requests so far: {usage_count}")


# ---------------- Web ----------------

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg = (data.get("message") or "").strip()
    user_id = str(data.get("user_id", "web_user"))

    if not msg:
        return jsonify({"reply": "Empty message"}), 400

    try:
        reply = ask_gemini(user_id, msg)
    except Exception:
        logger.exception("Gemini error (web)")
        reply = "Sorry, error talking to Gemini."

    return jsonify({"reply": reply})

@app.route("/health")
def health():
    return {"status": "ok", "usage": usage_count}


# ---------------- Runner ----------------

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

def main():
    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_cmd))
    telegram_app.add_handler(CommandHandler("usage", usage_cmd))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run Flask in background thread
    threading.Thread(target=run_flask, daemon=True).start()

    logger.info("Bot + Web UI started")
    telegram_app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()

