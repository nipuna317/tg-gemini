# Telegram + Gemini Bot (Long Polling)

## Setup
1. Create a Telegram bot with @BotFather and copy the token.
2. Create a Gemini API key in Google AI Studio.
3. Copy `.env.example` to `.env` and fill in the values.
4. Create and activate a virtual environment (optional but recommended).
5. Install dependencies.
6. Run the bot.

## Commands
- `/start` : welcome message
- `/help`  : usage

## Run (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env
python bot.py
```
