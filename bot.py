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
logger = logging.getLogger("BUNA_BONUS_P2P_BOT")

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8477592504:AAGjyhk0EPH4TTZ6pAb3o7M6obgTA15V5Z4")
ADMIN_ID = 7798227927  # የአድሚን ቴሌግራም ID

DEFAULT_RATE = 189.0  # 1 USDT = 189 ETB

# ለሁለቱም (Telebirr እና E-Birr) የሚያገለግለው አንድ ዓይነት ቁጥር እና ስም
PAYMENT_NUMBER = "0900253321"
ADMIN_NAME = "Bereket"
ADMIN_WALLET_ADDRESS = "TMAbfELuLH7gGyjp6YgUV1WWpPYwhaE27V"

MIN_USD = 20.0
MAX_USD = 600.0

ORDER_TIMEOUT_SECONDS = 30 * 60  # 30 ደቂቃ

(
    LANG,
    TRADE_TYPE,
    AMOUNT,
    BUY_PAYMENT_CHOICE,
    PAYMENT_CHOICE,
    SCREENSHOT,
    WALLET_ADDRESS,
    SELL_SCREENSHOT,
    SELL_TELEBIRR,
    SUPPORT_MSG,
) = range(10)

DB_FILE = "bot_data.db"

def init_db() -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value REAL
                )
            ''')
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('rate', ?)", (DEFAULT_RATE,))
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    trade_type TEXT,
                    amount_usd REAL,
                    total_birr REAL,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()
            cursor.execute("VACUUM;")
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

init_db()

def db_get_rate() -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'rate'")
            row = cursor.fetchone()
            return float(row[0]) if row else DEFAULT_RATE
    except Exception as e:
        logger.error(f"Error fetching rate: {e}")
        return DEFAULT_RATE

def record_user(user_id: int, username: str) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            conn.commit()
    except Exception as e:
        logger.error(f"Error recording user: {e}")

def record_order(user_id: int, trade_type: str, amount_usd: float, total_birr: float) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (user_id, trade_type, amount_usd, total_birr) VALUES (?, ?, ?, ?)",
                (user_id, trade_type, amount_usd, total_birr)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error recording order: {e}")

PERMANENT_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🔄 ዋና ሜኑ (Main Menu}")]],
    resize_keyboard=True
)

TEXTS = {
    'am': {
        'welcome': (
            "☕ <b>ቡና ቦነስ OFFICIAL P2P MARKET</b> ☕\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👋 <b>እንኳን ወደ ቡና ቦነስ P2P ገበያ ቦት በሰላም መጡ!</b>\n\n"
            "📊 <b>የዛሬው የምንዛሬ ተመን፦</b>\n"
            "└ <code>1 USDT = {rate:,.2f} ETB</code>\n\n"
            "💳 <b>የክፍያ መንገዶች:</b> <code>Telebirr | E-Birr</code>\n"
            "⚡ <i>ፈጣን፣ አስተማማኝ እና ሙሉ ደህንነቱ የተጠበቀ አገልግሎት!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>እባክዎን ማድረግ የሚፈልጉትን ይምረጡ፦</b>"
        ),
        'enter_amount_buy': (
            "🟢 <b>የግዢ መጠን ያስገቡ (BUY USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>የቀን የግዢ ወሰን፦</b>\n"
            "├ <b>አነስተኛ:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>ከፍተኛ:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>መግዛት የሚፈልጉትን የ USDT መጠን በቁጥር ብቻ ያስገቡ፦</i>"
        ),
        'enter_amount_sell': (
            "🔴 <b>የመሸጫ መጠን ያስገቡ (SELL USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>የቀን የመሸጫ ወሰን፦</b>\n"
            "├ <b>አነስተኛ:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>ከፍተኛ:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>መሸጥ የሚፈልጉትን የ USDT መጠን በቁጥር ብቻ ያስገቡ፦</i>"
        ),
        'invalid_num': "⚠️ <b>የተሳሳተ ቁጥር!</b>\nእባክዎን ከ <b>{min:,.2f}</b> እስከ <b>{max:,.2f} USDT</b> ባለው የቀን ወሰን ውስጥ ብቻ ያስገቡ፦",
        'select_pay_method': (
            "💳 <b>የክፍያ መንገድ ይምረጡ (Payment Method)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ለመግዛት የሚፈልጉበትን የክፍያ አማራጭ ከታች ይምረጡ፦"
        ),
        'summary_buy': (
            "🧾 <b>የግዢ ትዕዛዝ ማጠቃለያ (BUY RECEIPT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>የሚገዙት መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>የምንዛሬ ተመን:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>ጠቅላላ የሚከፍሉት:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>የክፍያ መንገድ:</b> <code>{method}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ለማረጋገጥና ወደ ክፍያ ለመሄድ ከታች ያለውን አዝራር ይጫኑ፦"
        ),
        'summary_sell': (
            "🧾 <b>የመሸጫ ትዕዛዝ ማጠቃለያ (SELL RECEIPT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>የሚሸጡት መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>የምንዛሬ ተመን:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>ጠቅላላ የሚቀበሉት:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>የክፍያ መንገድ:</b> <code>{method}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ለማረጋገጥና ወደ ክፍያ ለመሄድ ከታች ያለውን አዝራር ይጫኑ፦"
        ),
        'pay_instruct_buy': (
            "⏳ <b>የ 30 ደቂቃ ቆጠራ ጀምሯል!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 <b>የክፍያ መንገድ:</b> <code>{method}</code>\n"
            "👉 <b>የአድሚን ስልክ ቁጥር:</b> <code>{num}</code>\n"
            "👤 <b>ስም:</b> <code>{name}</code>\n\n"
            "💵 <b>የሚከፍሉት ትክክለኛ መጠን:</b> <code>{birr:,.2f} ETB</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>በ 30 ደቂቃ ውስጥ ካልከፈሉ ይህ ትዕዛዝ ይሰረዛል።</i>\n"
            "ክፍያውን እንደፈጸሙ የደረሰኙን <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        ),
        'pay_instruct_sell': (
            "⏳ <b>የ 30 ደቂቃ ቆጠራ ጀምሯል!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 <b>TRC20 Wallet Address:</b> <code>{wallet}</code>\n"
            "💎 <b>የሚልኩት ትክክለኛ መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>በ 30 ደቂቃ ውስጥ ካልላኩ ይህ ትዕዛዝ ይሰረዛል።</i>\n"
            "ከተላከ በኋላ የመላኪያውን <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        ),
        'got_ss_buy': "✅ <b>ደረሰኝዎ ደርሶናል!</b>\n\n🎯 አሁን USDT ገቢ የሚደረግበትን የ <b>TRC20 Wallet Address ወይም Binance Pay ID</b> ጽፈው ይላኩልን፦",
        'got_ss_sell': "✅ <b>ደረሰኝዎ ደርሶናል!</b>\n\n📱 አሁን ብር ገቢ የሚደረግበትን የ <b>ስልክ ቁጥር እና ሙሉ ስም</b> ጽፈው ይላኩልን፦",
        'complete': (
            "🎉 <b>ትዕዛዝዎ በስኬት ተላኳል!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ አድሚኖቻችን መረጃዎን በማረጋገጥ ላይ ናቸው። እንደተጠናቀቀ መልእክትና ማረጋገጫ ይደርስዎታል።\n"
            "እናመሰግናለን!"
        ),
        'support_prompt': "💬 <b>እገዛና ጥያቄ መስመር</b>\n━━━━━━━━━━━━━━━━━━━━━━\nያልገባዎትን ነገር፣ ጥያቄዎን ወይም አስተያየትዎን እዚህ ጽፈው ይላኩልን። አድሚኖቻችን በፍጥነት ይመልሱልዎታል።",
        'support_sent': "✅ መልእክትዎ ለአድሚን ተልኳል! በአጭር ጊዜ ውስጥ መልስ ይደርስዎታል።",
        'btn_cancel': "❌ ሰርዝ (Cancel)",
        'btn_support': "💬 እገዛና ጥያቄ (Support)"
    }
}

def get_txt(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return TEXTS['am']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    user = update.effective_user
    if user:
        record_user(user.id, user.username or "NoUsername")

    txt = get_txt(context)
    rate = db_get_rate()
    
    keyboard = [
        [InlineKeyboardButton("🟢 USDT መግዛት (Buy)", callback_data="trade_buy"), InlineKeyboardButton("🔴 USDT መሸጥ (Sell)", callback_data="trade_sell")],
        [InlineKeyboardButton(txt['btn_support'], callback_data="bot_support")]
    ]
    
    if update.message:
        await update.message.reply_text(txt['welcome'].format(rate=rate), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        await update.message.reply_text("💡 <i>ዋና ሜኑ</i>", reply_markup=PERMANENT_KEYBOARD, parse_mode="HTML")
    return TRADE_TYPE

async def select_trade_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        txt = get_txt(context)
        if query.data == "bot_support":
            await query.message.edit_text(txt['support_prompt'], parse_mode="HTML")
            return SUPPORT_MSG

        trade_type = query.data.split("_")[1]
        context.user_data['trade_type'] = trade_type
        
        keyboard = [[InlineKeyboardButton(txt['btn_cancel'], callback_data="user_cancel")]]
        msg = txt['enter_amount_buy'].format(min=MIN_USD, max=MAX_USD) if trade_type == 'buy' else txt['enter_amount_sell'].format(min=MIN_USD, max=MAX_USD)
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = get_txt(context)
    if not update.message or not update.message.text:
        return AMOUNT
    try:
        usd_amount = float(update.message.text)
        if usd_amount < MIN_USD or usd_amount > MAX_USD:
            await update.message.reply_text(txt['invalid_num'].format(min=MIN_USD, max=MAX_USD), parse_mode="HTML")
            return AMOUNT
        
        rate = db_get_rate()
        total_birr = usd_amount * rate
        context.user_data['usd_amount'] = usd_amount
        context.user_data['total_birr'] = total_birr

        keyboard = [
            [InlineKeyboardButton("📱 Telebirr", callback_data="pay_telebirr"), InlineKeyboardButton("📲 E-Birr", callback_data="pay_ebirr")],
            [InlineKeyboardButton(txt['btn_cancel'], callback_data="user_cancel")]
        ]
        await update.message.reply_text(txt['select_pay_method'], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return BUY_PAYMENT_CHOICE

    except ValueError:
        await update.message.reply_text(txt['invalid_num'].format(min=MIN_USD, max=MAX_USD), parse_mode="HTML")
        return AMOUNT

async def select_buy_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        txt = get_txt(context)
        method = query.data.split("_")[1]
        
        selected_method = "Telebirr" if method == "telebirr" else "E-Birr"
        context.user_data['payment_method'] = selected_method

        usd_amount = context.user_data.get('usd_amount', 0)
        total_birr = context.user_data.get('total_birr', 0)
        rate = db_get_rate()
        trade_type = context.user_data.get('trade_type', 'buy')

        keyboard = [
            [InlineKeyboardButton("አረጋግጥና ቀጥል ➡️", callback_data="proceed_pay")],
            [InlineKeyboardButton(txt['btn_cancel'], callback_data="user_cancel")]
        ]
        
        if trade_type == 'buy':
            msg = txt['summary_buy'].format(usd=usd_amount, rate=rate, birr=total_birr, method=selected_method)
        else:
            msg = txt['summary_sell'].format(usd=usd_amount, rate=rate, birr=total_birr, method=selected_method)
            
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return PAYMENT_CHOICE

async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        txt = get_txt(context)
        trade_type = context.user_data.get('trade_type', 'buy')
        total_birr = context.user_data.get('total_birr', 0)
        usd_amount = context.user_data.get('usd_amount', 0)
        method = context.user_data.get('payment_method', 'Telebirr')

        keyboard = [[InlineKeyboardButton(txt['btn_cancel'], callback_data="user_cancel")]]

        if trade_type == 'buy':
            msg = txt['pay_instruct_buy'].format(method=method, birr=total_birr, num=PAYMENT_NUMBER, name=ADMIN_NAME)
            await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return SCREENSHOT
        else:
            msg = txt['pay_instruct_sell'].format(usd=usd_amount, wallet=ADMIN_WALLET_ADDRESS)
            await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return SELL_SCREENSHOT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = get_txt(context)
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        await update.message.reply_text(txt['got_ss_buy'], parse_mode="HTML")
        return WALLET_ADDRESS
    return SCREENSHOT

async def receive_sell_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = get_txt(context)
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        await update.message.reply_text(txt['got_ss_sell'], parse_mode="HTML")
        return SELL_TELEBIRR
    return SELL_SCREENSHOT

async def receive_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = get_txt(context)
    if update.message and update.message.text:
        wallet = update.message.text
        user = update.effective_user
        usd = context.user_data.get('usd_amount', 0)
        birr = context.user_data.get('total_birr', 0)
        method = context.user_data.get('payment_method', 'Telebirr')

        if user:
            record_order(user.id, "BUY", usd, birr)

            admin_msg = (
                f"🚨 <b>አዲስ የግዢ ትዕዛዝ ደርሶናል!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>ተጠቃሚ:</b> @{user.username} (<code>{user.id}</code>)\n"
                f"💎 <b>መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
                f"💰 <b>ጠቅላላ ብር:</b> <code>{birr:,.2f} ETB</code>\n"
                f"📱 <b>የክፍያ መንገድ:</b> <code>{method}</code>\n"
                f"📍 <b>የተጠቃሚ ኪስ/አድራሻ:</b> <code>{wallet}</code>"
            )
            admin_btn = [
                [InlineKeyboardButton("✅ አረጋግጥ (Approve)", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ ውድቅ አድርግ (Reject)", callback_data=f"reject_{user.id}")]
            ]
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data['photo_file'], caption=admin_msg, reply_markup=InlineKeyboardMarkup(admin_btn), parse_mode="HTML")
        await update.message.reply_text(txt['complete'], parse_mode="HTML")
        context.user_data.clear()
        return ConversationHandler.END
    return WALLET_ADDRESS

async def receive_sell_telebirr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = get_txt(context)
    if update.message and update.message.text:
        telebirr_info = update.message.text
        user = update.effective_user
        usd = context.user_data.get('usd_amount', 0)
        birr = context.user_data.get('total_birr', 0)
        method = context.user_data.get('payment_method', 'Telebirr')

        if user:
            record_order(user.id, "SELL", usd, birr)

            admin_msg = (
                f"🚨 <b>አዲስ የመሸጫ ትዕዛዝ ደርሶናል!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>ተጠቃሚ:</b> @{user.username} (<code>{user.id}</code>)\n"
                f"💎 <b>መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
                f"💰 <b>ጠቅላላ ብር:</b> <code>{birr:,.2f} ETB</code>\n"
                f"📱 <b>የመቀበያ መንገድ ({method}):</b> <code>{telebirr_info}</code>"
            )
            admin_btn = [
                [InlineKeyboardButton("✅ አረጋግጥ (Approve)", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ ውድቅ አድርግ (Reject)", callback_data=f"reject_{user.id}")]
            ]
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data['photo_file'], caption=admin_msg, reply_markup=InlineKeyboardMarkup(admin_btn), parse_mode="HTML")
        await update.message.reply_text(txt['complete'], parse_mode="HTML")
        context.user_data.clear()
        return ConversationHandler.END
    return SELL_TELEBIRR

async def admin_decision_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
        data = query.data.split("_")
        action = data[0]
        target_user_id = int(data[1])

        if action == "approve":
            await context.bot.send_message(chat_id=target_user_id, text="🎉 <b>ትዕዛዝዎ በአድሚን ተረጋግጦ ተጠናቋል!</b>", parse_mode="HTML")
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n✅ <b>STATUS: APPROVED</b>", parse_mode="HTML")
        elif action == "reject":
            await context.bot.send_message(chat_id=target_user_id, text="❌ <b>ትዕዛዝዎ አልፀደቀም።</b>", parse_mode="HTML")
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n❌ <b>STATUS: REJECTED</b>", parse_mode="HTML")

async def cancel_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text("❌ <b>ትዕዛዙ ተሰርዟል።</b>\nእንደገና ለመጀመር /start ይበሉ።", parse_mode="HTML")
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    if not BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN missing.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    restart_handler = MessageHandler(filters.Regex("^🔄 ዋና ሜኑ"), start)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), restart_handler],
        states={
            TRADE_TYPE: [CallbackQueryHandler(select_trade_type, pattern="^(trade_|bot_support)")],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 ዋና ሜኑ"), get_amount)],
            BUY_PAYMENT_CHOICE: [CallbackQueryHandler(select_buy_payment, pattern="^pay_")],
            PAYMENT_CHOICE: [CallbackQueryHandler(payment_selected, pattern="^proceed_pay$")],
            SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
            WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 ዋና ሜኑ"), receive_wallet)],
            SELL_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_sell_screenshot)],
            SELL_TELEBIRR: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 ዋና ሜኑ"), receive_sell_telebirr)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_button_handler, pattern="^user_cancel$"),
            restart_handler,
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_decision_handler, pattern="^(approve_|reject_)"))

    logger.info("Buna Bonus P2P Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
