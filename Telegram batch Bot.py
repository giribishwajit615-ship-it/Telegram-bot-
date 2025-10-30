from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! 👋 Main ek naya Telegram bot hoon!")

app = ApplicationBuilder().token("8222645012:AAGng9jlzRI5G3idbwOX9-pFYXnnAbCLsKM").build()

app.add_handler(CommandHandler("start", start))

print("Bot running...")
app.run_polling()
