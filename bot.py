import os
import logging
import sqlite3
import threading
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai
from flask import Flask, request, jsonify, render_template

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

SYSTEM_INSTRUCTIONS = (
    "You are a friendly Sinhala “කෙලෙක්” assistant 😎\n"
    "- Reply in casual street Sinhala.\n"
    "- Keep answers short and clear.\n"
    "- Use light emojis sometimes 😂🔥😉.\n"
    "- Never give illegal or dangerous advice.\n"
)

WELCOME_TEXT = (
    "අඩෝ 😎 මම Gemini-powered bot එක.\n"
    "Message එකක් එවන්න — reply කරනවා.\n\n"
    "/remember <thing> - මට මතක තියාගන්න කියන්න\n"
    "/memory - මට තියෙන memory බලන්න\n"
    "/forget - memory clear කරන්න\n"
)

# ---------------- Memory DB ----------------

conn = sqlite3.connect("memory.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS memory (
    user_id INTEGER,
    key TEXT,
    value TEXT,
    PRIMARY KEY (user_id, key)
)
""")
conn.commit()

def save_memory(user_id: int, key: str, value: str):
    cur.execute(
        "INSERT OR REPLACE INTO memory (user_id, key, value) VALUES (?, ?, ?)",
        (user_id, key, value),
    )
    conn.commit()

def get_memory(user_id: int):
    cur.execute("SELECT key, value FROM memory WHERE user_id=?", (user_id,))
    return dict(cur.fetchall())

def clear_memory(user_id: int):
    cur.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
    conn.commit()

# ---------------- Gemini ----------------

def ask_gemini(text: str, memory: dict) -> str:
    mem_text = ""
    if memory:
        mem_text = "User memory:\n" + "\n".join([f"- {k}: {v}" for k, v in memory.items()])

    prompt = f"""{SYSTEM_INSTRUCTIONS}

{mem_text}

User: {text}
"""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text or "(No response)"

# ---------------- Telegram ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)

async def remember_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("අඩෝ 😅 මට මතක තියාගන්න දෙයක් දාන්න.")
        return
    save_memory(user_id, "note", text)
    await update.message.reply_text("හරි 😎 මතක තියාගත්ත!")

async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    mem = get_memory(user_id)
    if not mem:
        await update.message.reply_text("😅 මට ඔයා ගැන memory එකක් නෑ.")
        return
    lines = "\n".join([f"{k}: {v}" for k, v in mem.items()])
    await update.message.reply_text(f"🧠 මගේ memory:\n{lines}")

async def forget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    clear_memory(user_id)
    await update.message.reply_text("🗑️ හරි bro — memory clear කරා 😎")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    mem = get_memory(user_id)
    try:
        reply = ask_gemini(user_text, mem)
    except Exception:
        logger.exception("Gemini error")
        reply = "අඩෝ 😅 Gemini error එකක්."

    await update.message.reply_text(reply)

# ---------------- Web ----------------

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    msg = (data.get("message") or "").strip()
    user_id = data.get("user_id", 0)

    mem = get_memory(user_id)
    try:
        reply = ask_gemini(msg, mem)
    except Exception:
        logger.exception("Gemini error (web)")
        reply = "අඩෝ 😅 Gemini error එකක්."

    return jsonify({"reply": reply})

@app.route("/health")
def health():
    return {"status": "ok"}

# ---------------- Runner ----------------

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

def main():
    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("remember", remember_cmd))
    telegram_app.add_handler(CommandHandler("memory", memory_cmd))
    telegram_app.add_handler(CommandHandler("forget", forget_cmd))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    threading.Thread(target=run_flask, daemon=True).start()

    logger.info("Bot + Web + Memory started")
    telegram_app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
