# telegram_batch_bot.py

# Integrated /batch feature for admin-only Dropbox upload + Adrinolinks shortener
# IMPORTANT: Rotate the tokens you shared immediately if they are real.

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import telegram.error
import aiohttp
import asyncio
import uuid
import os
import json
import nest_asyncio
nest_asyncio.apply()
from datetime import datetime, timedelta

# -----------------------------
# CONFIG - replace if needed
# -----------------------------

TOKEN = os.environ.get("TG_BOT_TOKEN", "8222645012:AAGng9jlzRI5G3idbwOX9-pFYXnnAbCLsKM")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@CORNSEN")

# The Dropbox OAuth2 access token (the value you provided)
DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN", "sl.u.AGE2uiwoo15PePeNg1cxjsubfZz9HsMTKd2z3TL33ug4TGCluwKZQZYbrKduk-Z93F0_L4POI")

# Adrinolinks API token (the value you provided). You may need to change ADRINOLINKS_API_URL
ADRINOLINKS_TOKEN = os.environ.get("ADRINOLINKS_TOKEN", "5b33540e7eaa148b24b8cca0d9a5e1b9beb3e634")
ADRINOLINKS_API_URL = os.environ.get("ADRINOLINKS_API_URL", "https://adrinolinks.in/api/shorten")

# Admin Telegram user id (the value you provided). Keep as int
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "-7681308594"))

# Dropbox folder where to store uploaded videos
DROPBOX_BASE_FOLDER = os.environ.get("DROPBOX_BASE_FOLDER", "/batch_uploads")

# In-memory mapping: token -> {dropbox_path, shared_link, owner_admin, deleted, scheduled_delete_task}
TOKENS = {}

# Simple helper to make unique tokens
def make_token():
    return uuid.uuid4().hex

# -----------------------------
# Dropbox helper functions (async using aiohttp)
# -----------------------------

async def upload_to_dropbox(file_bytes: bytes, filename: str) -> str:
    """Upload bytes to Dropbox. Returns the Dropbox path (e.g. /batch_uploads/filename)"""
    path = f"{DROPBOX_BASE_FOLDER}/{uuid.uuid4().hex}_{filename}"
    url = "https://content.dropboxapi.com/2/files/upload"
    headers = {
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
        "Dropbox-API-Arg": json.dumps({"path": path, "mode": "add", "autorename": True, "mute": False}),
        "Content-Type": "application/octet-stream",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=file_bytes) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Dropbox upload failed: {resp.status} {text}")
            data = await resp.json()
            return data.get("path_display", path)

async def create_shared_link(dropbox_path: str) -> str:
    """Create a shared link for a Dropbox path. Returns the shared URL."""
    url = "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings"
    headers = {"Authorization": f"Bearer {DROPBOX_TOKEN}", "Content-Type": "application/json"}
    body = {"path": dropbox_path}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=body) as resp:
            text = await resp.text()
            if resp.status not in (200, 409):  # 409 may happen if link already exists
                raise RuntimeError(f"Dropbox create shared link failed: {resp.status} {text}")
            if resp.status == 200:
                data = json.loads(text)
                return data.get("url")

    # If link exists, fetch from list_shared_links
    list_url = "https://api.dropboxapi.com/2/sharing/list_shared_links"
    async with aiohttp.ClientSession() as session:
        async with session.post(list_url, headers=headers, json={"path": dropbox_path, "direct_only": True}) as resp:
            data = await resp.json()
            links = data.get("links", [])
            if links:
                return links[0].get("url")
            raise RuntimeError("Could not retrieve or create shared link")

async def delete_from_dropbox(dropbox_path: str):
    url = "https://api.dropboxapi.com/2/files/delete_v2"
    headers = {"Authorization": f"Bearer {DROPBOX_TOKEN}", "Content-Type": "application/json"}
    body = {"path": dropbox_path}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=body) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"Dropbox delete failed: {resp.status} {text}")

async def download_shared_link_bytes(shared_link: str) -> bytes:
    """Download file bytes from a Dropbox shared link."""
    url = "https://content.dropboxapi.com/2/sharing/get_shared_link_file"
    headers = {"Authorization": f"Bearer {DROPBOX_TOKEN}", "Dropbox-API-Arg": json.dumps({"url": shared_link})}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Dropbox download failed: {resp.status} {text}")
            return await resp.read()

# -----------------------------
# Adrinolinks helper
# -----------------------------

async def shorten_url_with_adrinolinks(long_url: str) -> str:
    """Shorten the URL using Adrinolinks (best effort)."""
    payload = {"api_key": ADRINOLINKS_TOKEN, "url": long_url}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ADRINOLINKS_API_URL, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"Adrinolinks shorten failed: {resp.status} {text}")
                    return long_url
                data = await resp.json()
                return data.get("short_url") or data.get("shortened") or data.get("url") or long_url
    except Exception as e:
        print("Adrinolinks request error:", e)
        return long_url
# -----------------------------
# Run the Telegram Bot
# -----------------------------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Example command handler (you can add /batch etc later)
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Bot is alive and ready ✅")

    app.add_handler(CommandHandler("start", start))

    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
