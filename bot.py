import os
import io
import sqlite3
import logging
import numpy as np
from PIL import Image
import easyocr

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# -----------------------------------------------------------------------------
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BUNA_BONUS_P2P_BOT")

logger.info("Initializing EasyOCR Engine...")
ocr_reader = easyocr.Reader(['en'], gpu=False)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7798227927"))

DEFAULT_RATE = 189.0  # 1 Buna Bonus = 189 ETB
TELEBIRR_NUMBER = "0900253321"
ADMIN_NAME = "Bereket"
ADMIN_WALLET_ADDRESS = "TMAbfELuLH7gGyjp6YgUV1WWpPYwhaE27V"

MIN_BONUS = 10.0
MAX_BONUS = 1000.0

(
    TRADE_TYPE,
    AMOUNT,
    BUY_PAYMENT_CHOICE,
    PAYMENT_CHOICE,
    SCREENSHOT,
    WALLET_ADDRESS,
    SELL_SCREENSHOT,
    SELL_TELEBIRR,
) = range(8)

DB_FILE = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('rate', ?)", (DEFAULT_RATE,))
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, trade_type TEXT, amount_bonus REAL, total_birr REAL)")
        conn.commit()

init_db()

def db_get_rate():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'rate'")
            row = cursor.fetchone()
            return float(row[0]) if row else DEFAULT_RATE
    except Exception:
        return DEFAULT_RATE

async def verify_screenshot_ai(photo_bytes: bytes, expected_amount: float):
    try:
        image = Image.open(io.BytesIO(photo_bytes))
        image_np = np.array(image)
        results = ocr_reader.readtext(image_np)
        extracted_text = " ".join([text for (_, text, _) in results])
        
        amt_str1 = f"{expected_amount:.2f}"
        amt_str2 = f"{int(expected_amount)}" if expected_amount.is_integer() else amt_str1

        if amt_str1 in extracted_text or amt_str2 in extracted_text:
            return "✅ **AI Verification:** Amount Matched in Screenshot!"
        return "⚠️ **AI Verification Warning:** Expected amount NOT detected clearly."
    except Exception:
        return "⚠️ **AI Verification Warning:** Could not read screenshot."

PERMANENT_KEYBOARD = ReplyKeyboardMarkup([[KeyboardButton("🔄 Main Menu / Restart")]], resize_keyboard=True)

# -----------------------------------------------------------------------------
# FLOW HANDLERS
# -----------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    rate = db_get_rate()
    
    welcome_text = (
        "☕ <b>BUNA BONUS OFFICIAL P2P MARKET</b> ☕\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👋 <b>እንኳን ወደ ቡና ቦነስ (Buna Bonus) P2P ገበያ በሰላም መጡ!</b>\n\n"
        f"📊 <b>የዛሬው የምንዛሬ ተመን፦</b>\n└ <code>1 Buna Bonus = {rate:,.2f} ETB</code>\n\n"
        "💳 <b>የክፍያ አማራጮች:</b> <code>Telebirr | CBE Bank</code>\n"
        "⚡ <i>ፈጣን፣ ታማኝ እና አስተማማኝ የቡና ቦነስ P2P አገልግሎት!</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>ለመጀመር ከታች የመገበያያ አማራጭ ይምረጡ፦</b>"
    )
    keyboard = [
        [InlineKeyboardButton("🟢 ቡና ቦነስ መግዛት (Buy)", callback_data="trade_buy"), InlineKeyboardButton("🔴 ቡና ቦነስ መሸጥ (Sell)", callback_data="trade_sell")]
    ]
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        await update.message.reply_text("💡 <i>ዋና ሜኑ</i>", reply_markup=PERMANENT_KEYBOARD, parse_mode="HTML")
    return TRADE_TYPE

async def select_trade_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    trade_type = query.data.split("_")[1]
    context.user_data['trade_type'] = trade_type
    
    msg = f"🟢 <b>የሚገዙትን የቡና ቦነስ መጠን ያስገቡ</b>\nወሰን: {MIN_BONUS} - {MAX_BONUS} Buna Bonus:" if trade_type == 'buy' else f"🔴 <b>የሚሸጡትን የቡና ቦነስ መጠን ያስገቡ</b>\nወሰን: {MIN_BONUS} - {MAX_BONUS} Buna Bonus:"
    await query.message.edit_text(msg, parse_mode="HTML")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        bonus_amount = float(update.message.text)
        if bonus_amount < MIN_BONUS or bonus_amount > MAX_BONUS:
            await update.message.reply_text(f"⚠️ እባክዎን ከ {MIN_BONUS} እስከ {MAX_BONUS} Buna Bonus ያስገቡ:")
            return AMOUNT
        
        rate = db_get_rate()
        total_birr = bonus_amount * rate
        context.user_data['bonus_amount'] = bonus_amount
        context.user_data['total_birr'] = total_birr
        
        if context.user_data.get('trade_type') == 'buy':
            keyboard = [
                [InlineKeyboardButton("📱 Telebirr", callback_data="pay_telebirr")],
                [InlineKeyboardButton("🏦 CBE Bank", callback_data="pay_cbe")]
            ]
            await update.message.reply_text("💳 <b>የክፍያ መንገድ ይምረጡ፦</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return BUY_PAYMENT_CHOICE
        else:
            keyboard = [[InlineKeyboardButton("አረጋግጥና ቀጥል ➡️", callback_data="proceed_pay")]]
            msg = f"🧾 <b>የመሸጫ ማጠቃለያ</b>\n\n☕ ቦነስ መጠን: <code>{bonus_amount:,.2f} Buna</code>\n📈 ተመን: <code>{rate:,.2f} ETB</code>\n💰 በቴሌብር የሚቀበሉት: <code>{total_birr:,.2f} ETB</code>"
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return PAYMENT_CHOICE
    except ValueError:
        await update.message.reply_text("⚠️ እባክዎን ትክክለኛ ቁጥር ያስገቡ!")
        return AMOUNT

async def select_buy_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[1].upper()
    context.user_data['payment_method'] = method
    
    bonus = context.user_data['bonus_amount']
    birr = context.user_data['total_birr']
    
    keyboard = [[InlineKeyboardButton("አረጋግጥና ቀጥል ➡️", callback_data="proceed_pay")]]
    msg = f"🧾 <b>የግዢ ማጠቃለያ</b>\n\n☕ ቦነስ መጠን: <code>{bonus:,.2f} Buna</code>\n💰 የሚከፍሉት: <code>{birr:,.2f} ETB</code>\n📱 የክፍያ መንገድ: <code>{method}</code>"
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return PAYMENT_CHOICE

async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    trade_type = context.user_data['trade_type']
    
    if trade_type == 'buy':
        birr = context.user_data['total_birr']
        method = context.user_data.get('payment_method', 'TELEBIRR')
        msg = f"⏳ <b>ክፍያ ይፈጽሙ</b>\n\n📱 {method}: <code>{TELEBIRR_NUMBER}</code> ({ADMIN_NAME})\n💵 የሚከፍሉት ትክክለኛ መጠን: <code>{birr:,.2f} ETB</code>\n\nክፍያውን ፈጽመው የደረሰኙን <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        await query.message.edit_text(msg, parse_mode="HTML")
        return SCREENSHOT
    else:
        bonus = context.user_data['bonus_amount']
        msg = f"⏳ <b>ቡና ቦነስ ይላኩ</b>\n\n☕ የቦነስ አድራሻ/ID: <code>{ADMIN_WALLET_ADDRESS}</code>\n☕ የሚልኩት መጠን: <code>{bonus:,.2f} Buna Bonus</code>\n\nየተላከበትን <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        await query.message.edit_text(msg, parse_mode="HTML")
        return SELL_SCREENSHOT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        photo_obj = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_obj.download_as_bytearray()
        
        ai_status = await verify_screenshot_ai(photo_bytes, context.user_data['total_birr'])
        context.user_data['ai_status'] = ai_status
        
        await update.message.reply_text("✅ ደረሰኝ ደርሶናል!\n\n🎯 አሁን ቡና ቦነሱ ገቢ የሚደረግበትን የ <b>Buna Wallet Address / ID / Phone</b> ይላኩ፦")
        return WALLET_ADDRESS
    return SCREENSHOT

async def receive_sell_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        photo_obj = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_obj.download_as_bytearray()
        
        ai_status = await verify_screenshot_ai(photo_bytes, context.user_data['bonus_amount'])
        context.user_data['ai_status'] = ai_status
        
        await update.message.reply_text("✅ ደረሰኝ ደርሶናል!\n\n📱 አሁን ብር ገቢ የሚደረግበትን የ <b>Telebirr ስልክ ቁጥር እና ሙሉ ስም</b> ይላኩ፦")
        return SELL_TELEBIRR
    return SELL_SCREENSHOT

async def receive_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text
    user = update.effective_user
    bonus = context.user_data['bonus_amount']
    birr = context.user_data['total_birr']
    
    admin_msg = f"🚨 <b>NEW BUY ORDER (BUNA BONUS)!</b>\n\n👤 User: @{user.username} (<code>{user.id}</code>)\n☕ Bonus Amount: <code>{bonus} Buna</code>\n💰 Birr Paid: <code>{birr} ETB</code>\n📍 User Buna Wallet: <code>{wallet}</code>\n\n🤖 AI Audit: {context.user_data['ai_status']}"
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data['photo_file'], caption=admin_msg, parse_mode="HTML")
    await update.message.reply_text("🎉 ትዕዛዝዎ በስኬት ተልኳል! አድሚን መረጃውን አረጋግጦ ቡና ቦነሱን ገቢ ያደርግልዎታል።")
    context.user_data.clear()
    return ConversationHandler.END

async def receive_sell_telebirr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telebirr = update.message.text
    user = update.effective_user
    bonus = context.user_data['bonus_amount']
    birr = context.user_data['total_birr']
    
    admin_msg = f"🚨 <b>NEW SELL ORDER (BUNA BONUS)!</b>\n\n👤 User: @{user.username} (<code>{user.id}</code>)\n☕ Bonus Sold: <code>{bonus} Buna</code>\n💰 Birr to Pay: <code>{birr} ETB</code>\n📱 User Telebirr: <code>{telebirr}</code>\n\n🤖 AI Audit: {context.user_data['ai_status']}"
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data['photo_file'], caption=admin_msg, parse_mode="HTML")
    await update.message.reply_text("🎉 ትዕዛዝዎ በስኬት ተልኳል! አድሚን መረጃውን አረጋግጦ ብሩን በቴሌብር ይልክልዎታል።")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    restart_handler = MessageHandler(filters.Regex("^🔄 Main Menu / Restart$"), start)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), restart_handler],
        states={
            TRADE_TYPE: [CallbackQueryHandler(select_trade_type, pattern="^trade_")],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu / Restart$"), get_amount)],
            BUY_PAYMENT_CHOICE: [CallbackQueryHandler(select_buy_payment, pattern="^pay_")],
            PAYMENT_CHOICE: [CallbackQueryHandler(payment_selected, pattern="^proceed_pay$")],
            SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
            WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu / Restart$"), receive_wallet)],
            SELL_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_sell_screenshot)],
            SELL_TELEBIRR: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu / Restart$"), receive_sell_telebirr)],
        },
        fallbacks=[restart_handler],
    )

    app.add_handler(conv_handler)
    print("Buna Bonus Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
