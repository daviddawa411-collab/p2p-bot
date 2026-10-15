import os
import io
import sqlite3
import logging

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
logger = logging.getLogger("USDT_P2P_BOT")

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8477592504:AAGjyhk0EPH4TTZ6pAb3o7M6obgTA15V5Z4")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7798227927"))

DEFAULT_RATE = 189.0  # 1 USDT = 189 ETB
TELEBIRR_NUMBER = "0900253321"
ADMIN_NAME = "Bereket"
ADMIN_WALLET_ADDRESS = "TMAbfELuLH7gGyjp6YgUV1WWpPYwhaE27V"

MIN_USDT = 5.0
MAX_USDT = 5000.0

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
        cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, trade_type TEXT, amount_usdt REAL, total_birr REAL)")
        conn.commit()
    
    try:
        vac_conn = sqlite3.connect(DB_FILE)
        vac_conn.isolation_level = None
        vac_conn.execute("VACUUM;")
        vac_conn.close()
    except Exception:
        pass

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

PERMANENT_KEYBOARD = ReplyKeyboardMarkup([[KeyboardButton("🔄 Main Menu / ጀማሪ ገጽ")]], resize_keyboard=True)

# -----------------------------------------------------------------------------
# FLOW HANDLERS
# -----------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    rate = db_get_rate()
    
    welcome_text = (
        "💎 <b>OFFICIAL USDT P2P MARKET</b> 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>እንኳን ወደ ፈጣኑ እና ደህንነቱ የተጠበቀ የ USDT P2P ገበያ በሰላም መጡ!</b>\n\n"
        f"📊 <b>የዛሬው የምንዛሬ ተመን፦</b>\n└ <code>1 USDT = {rate:,.2f} ETB</code>\n\n"
        "💳 <b>የክፍያ አማራጮች:</b> <code>Telebirr | CBE Bank</code>\n"
        "⚡ <i>ፈጣን ክፍያ እና አስተማማኝ የ P2P ግብይት!</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>ለመጀመር ከታች ካሉት አማራጮች አንዱን ይምረጡ፦</b>"
    )
    keyboard = [
        [InlineKeyboardButton("🟢 USDT መግዛት (Buy)", callback_data="trade_buy"), InlineKeyboardButton("🔴 USDT መሸጥ (Sell)", callback_data="trade_sell")]
    ]
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        await update.message.reply_text("💡 <i>ማንኛውንም ግብይት ለማቋረጥ ወይም ወደ መጀመሪያው ለመመለስ ከታች ያለውን ቁልፍ ይጠቀሙ።</i>", reply_markup=PERMANENT_KEYBOARD, parse_mode="HTML")
    return TRADE_TYPE

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 <b>የ P2P ቦት መመሪያ (Help Desk)</b>\n\n"
        "1️⃣ <b>USDT ለመግዛት:</b> 'USDT መግዛት' የሚለውን በመንካት የሚፈልጉትን መጠን ያስገቡ፣ ክፍያውን ፈጽመው የደረሰኝ ፎቶ ይላኩ።\n"
        "2️⃣ <b>USDT ለመሸጥ:</b> 'USDT መሸጥ' የሚለውን በመንካት መጠኑን ያስገቡ፣ አድራሻችን ላይ ዶላሩን ልከው የደረሰኝ ፎቶ ይላኩ።\n"
        "3️⃣ <b>ድጋፍ (Support):</b> ለጥያቄዎ አድሚኑን በቀጥታ ማግኘት ይችላሉ።"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def select_trade_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    trade_type = query.data.split("_")[1]
    context.user_data['trade_type'] = trade_type
    
    msg = f"🟢 <b>ሊገዙት የሚፈልጉትን የ USDT መጠን ያስገቡ</b>\nወሰን: {MIN_USDT} - {MAX_USDT} USDT:" if trade_type == 'buy' else f"🔴 <b>ሊሸጡት የሚፈልጉትን የ USDT መጠን ያስገቡ</b>\nወሰን: {MIN_USDT} - {MAX_USDT} USDT:"
    await query.message.edit_text(msg, parse_mode="HTML")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        usdt_amount = float(update.message.text)
        if usdt_amount < MIN_USDT or usdt_amount > MAX_USDT:
            await update.message.reply_text(f"⚠️ እባክዎን ከ {MIN_USDT} እስከ {MAX_USDT} USDT መካከል ያስገቡ:")
            return AMOUNT
        
        rate = db_get_rate()
        total_birr = usdt_amount * rate
        context.user_data['usdt_amount'] = usdt_amount
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
            msg = f"🧾 <b>የመሸጫ ማጠቃለያ</b>\n\n💎 USDT መጠን: <code>{usdt_amount:,.2f} USDT</code>\n📈 ተመን: <code>{rate:,.2f} ETB</code>\n💰 የሚቀበሉት ብር: <code>{total_birr:,.2f} ETB</code>"
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return PAYMENT_CHOICE
    except ValueError:
        await update.message.reply_text("⚠️ እባክዎን ትክክለኛ የቁጥር መጠን ያስገቡ!")
        return AMOUNT

async def select_buy_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[1].upper()
    context.user_data['payment_method'] = method
    
    usdt = context.user_data['usdt_amount']
    birr = context.user_data['total_birr']
    
    keyboard = [[InlineKeyboardButton("አረጋግጥና ቀጥል ➡️", callback_data="proceed_pay")]]
    msg = f"🧾 <b>የግዢ ማጠቃለያ</b>\n\n💎 USDT መጠን: <code>{usdt:,.2f} USDT</code>\n💰 የሚከፍሉት ብር: <code>{birr:,.2f} ETB</code>\n📱 የክፍያ መንገድ: <code>{method}</code>"
    await query.message.edit_text(msg, parse_mode="HTML")
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
        usdt = context.user_data['usdt_amount']
        msg = f"⏳ <b>USDT ልከው ያረጋግጡ</b>\n\n💎 TRC20 አድራሻ: <code>{ADMIN_WALLET_ADDRESS}</code>\n💎 የሚልኩት መጠን: <code>{usdt:,.2f} USDT</code>\n\nየተላከበትን <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        await query.message.edit_text(msg, parse_mode="HTML")
        return SELL_SCREENSHOT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        await update.message.reply_text("✅ ደረሰኝዎ ደርሶናል!\n\n🎯 አሁን USDT ገቢ የሚደረግበትን የ <b>TRC20 Wallet Address</b> ይላኩ፦")
        return WALLET_ADDRESS
    return SCREENSHOT

async def receive_sell_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        await update.message.reply_text("✅ ደረሰኝዎ ደርሶናል!\n\n📱 አሁን ብር ገቢ የሚደረግበትን የ <b>Telebirr ስልክ ቁጥር እና ሙሉ ስም</b> ይላኩ፦")
        return SELL_TELEBIRR
    return SELL_SCREENSHOT

async def receive_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text
    user = update.effective_user
    usdt = context.user_data['usdt_amount']
    birr = context.user_data['total_birr']
    
    admin_msg = (
        f"🚨 <b>NEW BUY ORDER (USDT)!</b>\n\n"
        f"👤 <b>User:</b> @{user.username} (<code>{user.id}</code>)\n"
        f"💎 <b>USDT Amount:</b> <code>{usdt} USDT</code>\n"
        f"💰 <b>Birr Paid:</b> <code>{birr} ETB</code>\n"
        f"📍 <b>TRC20 Wallet:</b> <code>{wallet}</code>"
    )
    admin_btn = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
    ]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data['photo_file'], caption=admin_msg, reply_markup=InlineKeyboardMarkup(admin_btn), parse_mode="HTML")
    await update.message.reply_text("🎉 ትዕዛዝዎ በስኬት ተልኳል! አድሚን መረጃውን አረጋግጦ USDT ይልክልዎታል።")
    context.user_data.clear()
    return ConversationHandler.END

async def receive_sell_telebirr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telebirr = update.message.text
    user = update.effective_user
    usdt = context.user_data['usdt_amount']
    birr = context.user_data['total_birr']
    
    admin_msg = (
        f"🚨 <b>NEW SELL ORDER (USDT)!</b>\n\n"
        f"👤 <b>User:</b> @{user.username} (<code>{user.id}</code>)\n"
        f"💎 <b>USDT Sold:</b> <code>{usdt} USDT</code>\n"
        f"💰 <b>Birr to Pay:</b> <code>{birr} ETB</code>\n"
        f"📱 <b>Telebirr Info:</b> <code>{telebirr}</code>"
    )
    admin_btn = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")]
    ]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data['photo_file'], caption=admin_msg, reply_markup=InlineKeyboardMarkup(admin_btn), parse_mode="HTML")
    await update.message.reply_text("🎉 ትዕዛዝዎ በስኬት ተልኳል! አድሚን መረጃውን አረጋግጦ ብሩን በቴሌብር ይልክልዎታል።")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_decision_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    action = data[0]
    target_user_id = int(data[1])

    if action == "approve":
        await context.bot.send_message(chat_id=target_user_id, text="🎉 <b>ትዕዛዝዎ በአድሚን ተረጋግጦ ተጠናቋል!</b>", parse_mode="HTML")
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n✅ <b>STATUS: APPROVED</b>", parse_mode="HTML")
    elif action == "reject":
        await context.bot.send_message(chat_id=target_user_id, text="❌ <b>ትዕዛዝዎ አልጸደቀም። እባክዎን አድሚንን ያናግሩ።</b>", parse_mode="HTML")
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n❌ <b>STATUS: REJECTED</b>", parse_mode="HTML")

def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    restart_handler = MessageHandler(filters.Regex("^🔄 Main Menu"), start)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), restart_handler],
        states={
            TRADE_TYPE: [CallbackQueryHandler(select_trade_type, pattern="^trade_")],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), get_amount)],
            BUY_PAYMENT_CHOICE: [CallbackQueryHandler(select_buy_payment, pattern="^pay_")],
            PAYMENT_CHOICE: [CallbackQueryHandler(payment_selected, pattern="^proceed_pay$")],
            SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
            WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), receive_wallet)],
            SELL_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_sell_screenshot)],
            SELL_TELEBIRR: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), receive_sell_telebirr)],
        },
        fallbacks=[restart_handler],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(admin_decision_handler, pattern="^(approve_|reject_)"))
    
    print("USDT P2P Bot is running smoothly...")
    app.run_polling()

if __name__ == "__main__":
    main()
