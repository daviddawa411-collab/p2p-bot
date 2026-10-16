import os
import io
import sqlite3
import logging
import numpy as np
from PIL import Image
import easyocr

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
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

# AI OCR Reader Initialization
logger.info("Initializing AI OCR Engine...")
ocr_reader = easyocr.Reader(['en'], gpu=False)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8477592504:AAGjyhk0EPH4TTZ6pAb3o7M6obgTA15V5Z4")
ADMIN_ID = 7798227927  # Admin Telegram ID

DEFAULT_RATE = 189.0  # 1 USDT = 189 ETB

PAYMENT_NUMBER = "0900253321"
ADMIN_NAME = "Bereket"
ADMIN_WALLET_ADDRESS = "TMAbfELuLH7gGyjp6YgUV1WWpPYwhaE27V"

MIN_USD = 20.0
MAX_USD = 600.0

ORDER_TIMEOUT_SECONDS = 30 * 60  # 30 minutes

(
    LANG,
    TRADE_TYPE,
    AMOUNT,
    PAYMENT_CHOICE,
    SCREENSHOT,
    WALLET_ADDRESS,
    SELL_SCREENSHOT,
    SELL_TELEBIRR,
    SUPPORT_MSG,
) = range(9)

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

async def verify_screenshot_ai(photo_bytes: bytes, expected_amount: float) -> tuple[bool, str]:
    try:
        image = Image.open(io.BytesIO(photo_bytes))
        image_np = np.array(image)
        results = ocr_reader.readtext(image_np)
        
        extracted_text = " ".join([text for (_, text, _) in results])
        logger.info(f"AI Extracted Text: {extracted_text}")

        formatted_amount_1 = f"{expected_amount:.2f}"
        formatted_amount_2 = f"{int(expected_amount)}" if expected_amount.is_integer() else f"{expected_amount:.2f}"

        if formatted_amount_1 in extracted_text or formatted_amount_2 in extracted_text:
            return True, "✅ **AI Audit:** Amount verified successfully!"
        else:
            return False, "⚠️ **AI Warning:** Amount not clearly detected. Please check manually!"
    except Exception as e:
        logger.error(f"AI Verification Error: {e}")
        return False, "⚠️ **AI Warning:** Could not read image. Please check manually."

PERMANENT_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🔄 Main Menu / ቋንቋ መቀየሪያ / Beddali / Menu")]],
    resize_keyboard=True
)

TEXTS = {
    'am': {
        'welcome': (
            "☕ <b>BUNA BONUS OFFICIAL P2P MARKET</b> ☕\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👋 <b>እንኳን ወደ ቡና ቦነስ P2P ገበያ በሰላም መጡ!</b>\n\n"
            "📊 <b>የዛሬው የምንዛሬ ተመን፦</b>\n"
            "└ <code>1 USDT = {rate:,.2f} ETB</code>\n\n"
            "💳 <b>የክፍያ መንገድ:</b> <code>Telebirr</code>\n"
            "⚡ <i>ፈጣን ክፍያ እና አስተማማኝ P2P ግብይት!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>እባክዎን የሚፈልጉትን አማራጭ ይምረጡ፦</b>"
        ),
        'buy_btn': "🟢 USDT መግዛት (Buy)",
        'sell_btn': "🔴 USDT መሸጥ (Sell)",
        'webapp_btn': "🚀 Buna Bonus Mini App ဖွင့်ရန်",
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
        'invalid_num': "⚠️ <b>የተሳሳተ ቁጥር!</b>\nእባክዎን ከ <b>{min:,.2f}</b> እስከ <b>{max:,.2f} USDT</b> ባለው ወሰን ውስጥ ያስገቡ፦",
        'summary_buy': (
            "🧾 <b>የግዢ ማጠቃለያ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>ተመን:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>ጠቅላላ ክፍያ:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>ክፍያ:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ለማረጋገጥ ከታች ያለውን ይጫኑ፦"
        ),
        'summary_sell': (
            "🧾 <b>የመሸጫ ማጠቃለያ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>ተመን:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>የሚቀበሉት:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>ክፍያ:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ለማረጋገጥ ከታች ያለውን ይጫኑ፦"
        ),
        'pay_instruct_buy': (
            "⏳ <b>የ 30 ደቂቃ ቆጠራ ጀምሯል!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 <b>የክፍያ መንገድ:</b> <code>Telebirr</code>\n"
            "👉 <b>ቁጥር:</b> <code>{num}</code>\n"
            "👤 <b>ስም:</b> <code>{name}</code>\n\n"
            "💵 <b>የሚከፍሉት ትክክለኛ መጠን:</b> <code>{birr:,.2f} ETB</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>በ 30 ደቂቃ ውስጥ ካልከፈሉ ትዕዛዙ ይሰረዛል።</i>\n"
            "ክፍያውን ፈጸመው <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        ),
        'pay_instruct_sell': (
            "⏳ <b>የ 30 ደቂቃ ቆጠራ ጀምሯል!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 <b>TRC20 Wallet Address:</b> <code>{wallet}</code>\n"
            "💎 <b>የሚልኩት መጠን:</b> <code>{usd:,.2f} USDT</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>በ 30 ደቂቃ ውስጥ ካልላኩ ትዕዛዙ ይሰረዛል።</i>\n"
            "ከተላከ በኋላ <b>Screenshot (ፎቶ)</b> እዚህ ይላኩ፦"
        ),
        'got_ss_buy': "✅ <b>ደረሰኝዎ ደርሶናል! AI በማረጋገጥ ላይ ነው...</b>\n\n🎯 አሁን USDT ገቢ የሚደረግበትን <b>TRC20 Address ወይም Binance Pay ID</b> ይላኩልን፦",
        'got_ss_sell': "✅ <b>ደረሰኝዎ ደርሶናል! AI በማረጋገጥ ላይ ነው...</b>\n\n📱 አሁን ብር ገቢ የሚደረግበትን <b>Telebirr ቁጥር እና ስም</b> ይላኩልን፦",
        'complete': "🎉 <b>ትዕዛዝዎ በስኬት ተልኳል!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n⏳ አድሚን በማረጋገጥ ላይ ነው። እናመሰግናለን!",
        'support_prompt': "💬 <b>እገዛ ማዕከል</b>\n━━━━━━━━━━━━━━━━━━━━━━\nጥያቄዎን ወይም አስተያየትዎን እዚህ ይጻፉ።",
        'support_sent': "✅ መልእክትዎ ለአድሚን ተልኳል!",
        'btn_cancel': "❌ ሰርዝ (Cancel)",
        'btn_support': "💬 እገዛ (Support)"
    },
    'om': {
        'welcome': (
            "☕ <b>BUNA BONUS OFFICIAL P2P MARKET</b> ☕\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ <b>Gara gabaa Buna Bonus P2P saffisaa fi amanamaa ta'etti nagaan dhuftan!</b>\n\n"
            "📊 <b>Gatii Jijjiirraa Har'aa፦</b>\n"
            "└ <code>1 USDT = {rate:,.2f} ETB</code>\n\n"
            "💳 <b>Karaa Kaffaltii:</b> <code>Telebirr</code>\n"
            "⚡ <i>Kaffaltii saffisaa fi daldala P2P amanamaa!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>Maaloo filannoo barbaaddan filadhaa፦</b>"
        ),
        'buy_btn': "🟢 USDT Bitachuu (Buy)",
        'sell_btn': "🔴 USDT Gurguruu (Sell)",
        'webapp_btn': "🚀 Buna Bonus Mini App Bani",
        'enter_amount_buy': (
            "🟢 <b>Hanga Bitachuu Barbaaddan Galchaa (BUY USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Daangaa Guyyaa፦</b>\n"
            "├ <b>Xiqqaa:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>Guddaa:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>Hanga bitachuu barbaaddan lakkoofsaan qofa galchaa፦</i>"
        ),
        'enter_amount_sell': (
            "🔴 <b>Hanga Gurguruu Barbaaddan Galchaa (SELL USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Daangaa Guyyaa፦</b>\n"
            "├ <b>Xiqqaa:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>Guddaa:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>Hanga gurguruu barbaaddan lakkoofsaan qofa galchaa፦</i>"
        ),
        'invalid_num': "⚠️ <b>Lakkoofsa Dogoggoraa!</b>\nMaaloo <b>{min:,.2f}</b> hanga <b>{max:,.2f} USDT</b> jidduutti galchaa፦",
        'summary_buy': (
            "🧾 <b>Cuunfaa Bittaa</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Hanga:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>Gatii:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>Waliigala Kaffaltii:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>Kaffaltii:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Mirkaneessuuf cuqaasaa:"
        ),
        'summary_sell': (
            "🧾 <b>Cuunfaa Gurgurtaaa</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Hanga:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>Gatii:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>Waliigala Fudhattan:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>Kaffaltii:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Mirkaneessuuf cuqaasaa:"
        ),
        'pay_instruct_buy': (
            "⏳ <b>Yeroon Daqiiqaa 30 Jalqabeera!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 <b>Kaffaltii:</b> <code>Telebirr</code>\n"
            "👉 <b>Lakkoofsa Admin:</b> <code>{num}</code>\n"
            "👤 <b>Maqaa:</b> <code>{name}</code>\n\n"
            "💵 <b>Hanga Kaffaltii:</b> <code>{birr:,.2f} ETB</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>Daqiiqaa 30 keessatti yoo kaffaltii hin raawwatin ajajni ni haqama.</i>\n"
            "Kaffaltii raawwattanii <b>Screenshot (Suuraa)</b> asitti ergaa:"
        ),
        'pay_instruct_sell': (
            "⏳ <b>Yeroon Daqiiqaa 30 Jalqabeera!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 <b>TRC20 Wallet Address:</b> <code>{wallet}</code>\n"
            "💎 <b>Hanga Ergitan:</b> <code>{usd:,.2f} USDT</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>Daqiiqaa 30 keessatti yoo hin ergine ajajni ni haqama.</i>\n"
            "Ergitan booda <b>Screenshot (Suuraa)</b> asitti ergaa:"
        ),
        'got_ss_buy': "✅ <b>Nagaheen keessan nu gaheera! AI mirkaneessaa jira...</b>\n\n🎯 Amma <b>TRC20 Address ykn Binance Pay ID</b> keessan ergaa:",
        'got_ss_sell': "✅ <b>Nagaheen keessan nu gaheera! AI mirkaneessaa jira...</b>\n\n📱 Amma <b>Lakkoofsa Telebirr fi Maqaa</b> keessan ergaa:",
        'complete': "🎉 <b>Ajajni keessan milkaa'inaan ergameera!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n⏳ Admin ni mirkaneessa. Galatoomaa!",
        'support_prompt': "💬 <b>Giddugala Deeggarsa</b>\n━━━━━━━━━━━━━━━━━━━━━━\nGaaffii keessan asitti barreessaa.",
        'support_sent': "✅ Ergaan keessan Adminif ergameera!",
        'btn_cancel': "❌ Haqi (Cancel)",
        'btn_support': "💬 Deeggarsa (Support)"
    },
    'en': {
        'welcome': (
            "☕ <b>BUNA BONUS OFFICIAL P2P MARKET</b> ☕\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ <b>Welcome to Buna Bonus Official P2P Market!</b>\n\n"
            "📊 <b>Today's Exchange Rate:</b>\n"
            "└ <code>1 USDT = {rate:,.2f} ETB</code>\n\n"
            "💳 <b>Payment Method:</b> <code>Telebirr</code>\n"
            "⚡ <i>Fast payment and secure P2P trading!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>Please select your preferred option:</b>"
        ),
        'buy_btn': "🟢 Buy USDT",
        'sell_btn': "🔴 Sell USDT",
        'webapp_btn': "🚀 Open Buna Bonus Mini App",
        'enter_amount_buy': (
            "🟢 <b>Enter Amount to Buy (BUY USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Daily Limits:</b>\n"
            "├ <b>Min:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>Max:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>Enter amount in numbers only:</i>"
        ),
        'enter_amount_sell': (
            "🔴 <b>Enter Amount to Sell (SELL USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Daily Limits:</b>\n"
            "├ <b>Min:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>Max:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>Enter amount in numbers only:</i>"
        ),
        'invalid_num': "⚠️ <b>Invalid Amount!</b>\nPlease enter between <b>{min:,.2f}</b> and <b>{max:,.2f} USDT</b>:",
        'summary_buy': (
            "🧾 <b>Buy Summary</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Amount:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>Rate:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>Total Payable:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>Payment:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Click below to proceed:"
        ),
        'summary_sell': (
            "🧾 <b>Sell Summary</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Amount:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>Rate:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>Total Receivable:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>Payment:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Click below to proceed:"
        ),
        'pay_instruct_buy': (
            "⏳ <b>30 Minutes Timer Started!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 <b>Payment Method:</b> <code>Telebirr</code>\n"
            "👉 <b>Admin Number:</b> <code>{num}</code>\n"
            "👤 <b>Name:</b> <code>{name}</code>\n\n"
            "💵 <b>Exact Amount to Pay:</b> <code>{birr:,.2f} ETB</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>If payment is not sent within 30 mins, order will be cancelled.</i>\n"
            "Send payment <b>Screenshot</b> here:"
        ),
        'pay_instruct_sell': (
            "⏳ <b>30 Minutes Timer Started!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 <b>TRC20 Wallet Address:</b> <code>{wallet}</code>\n"
            "💎 <b>Exact Amount to Send:</b> <code>{usd:,.2f} USDT</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>If USDT is not sent within 30 mins, order will be cancelled.</i>\n"
            "Send transfer <b>Screenshot</b> here:"
        ),
        'got_ss_buy': "✅ <b>Screenshot received! AI is auditing...</b>\n\n🎯 Now reply with your <b>TRC20 Address or Binance Pay ID</b>:",
        'got_ss_sell': "✅ <b>Screenshot received! AI is auditing...</b>\n\n📱 Now reply with your <b>Telebirr Number and Name</b>:",
        'complete': "🎉 <b>Order submitted successfully!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n⏳ Admin is verifying. Thank you!",
        'support_prompt': "💬 <b>Help & Support</b>\n━━━━━━━━━━━━━━━━━━━━━━\nPlease type your message below.",
        'support_sent': "✅ Your message has been sent to Admin!",
        'btn_cancel': "❌ Cancel",
        'btn_support': "💬 Support"
    },
    'so': {
        'welcome': (
            "☕ <b>BUNA BONUS OFFICIAL P2P MARKET</b> ☕\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ <b>Ku soo dhowow Buna Bonus Official P2P Market!</b>\n\n"
            "📊 <b>Qiimaha Sarifka Maanta፦</b>\n"
            "└ <code>1 USDT = {rate:,.2f} ETB</code>\n\n"
            "💳 <b>Habka Bixinta:</b> <code>Telebirr</code>\n"
            "⚡ <i>Bixin degdeg ah iyo ganacsi P2P lagu kalsoonaan karo!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>Fadlan dooro adeegga aad rabto፦</b>"
        ),
        'buy_btn': "🟢 Iibso USDT (Buy)",
        'sell_btn': "🔴 Iibi USDT (Sell)",
        'webapp_btn': "🚀 Fur Buna Bonus Mini App",
        'enter_amount_buy': (
            "🟢 <b>Gali inta aad iibsanirabto (BUY USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Xadka Maalinlaha ah፦</b>\n"
            "├ <b>Ugu Yaraan:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>Ugu Badnaan:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>Gali qadarka nambar keliya ahaan፦</i>"
        ),
        'enter_amount_sell': (
            "🔴 <b>Gali inta aad iibin rabto (SELL USDT)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>Xadka Maalinlaha ah፦</b>\n"
            "├ <b>Ugu Yaraan:</b> <code>{min:,.2f} USDT</code>\n"
            "└ <b>Ugu Badnaan:</b> <code>{max:,.2f} USDT</code>\n\n"
            "✍️ <i>Gali qadarka nambar keliya ahaan፦</i>"
        ),
        'invalid_num': "⚠️ <b>Nambar khaldan!</b>\nFadlan gali int u dhaxeysa <b>{min:,.2f}</b> iyo <b>{max:,.2f} USDT</b>:",
        'summary_buy': (
            "🧾 <b>Koobitaanka Iibsiga</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Qadarka:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>Sarifka:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>Wadarta Lacagta:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>Lacag Bixinta:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Riix hoos si aad u sii waddo:"
        ),
        'summary_sell': (
            "🧾 <b>Koobitaanka Iibinta</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <b>Qadarka:</b> <code>{usd:,.2f} USDT</code>\n"
            "📈 <b>Sarifka:</b> <code>{rate:,.2f} ETB</code>\n"
            "💰 <b>Wadarta aad heleysid:</b> <code>{birr:,.2f} ETB</code>\n"
            "📱 <b>Lacag Bixinta:</b> <code>Telebirr</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Riix hoos si aad u sii waddo:"
        ),
        'pay_instruct_buy': (
            "⏳ <b>Waqtiga 30 daqiiqo waa bilowday!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 <b>Habka Bixinta:</b> <code>Telebirr</code>\n"
            "👉 <b>Nambarka Admin:</b> <code>{num}</code>\n"
            "👤 <b>Magaca:</b> <code>{name}</code>\n\n"
            "💵 <b>Lacagta saxda ah:</b> <code>{birr:,.2f} ETB</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>Haddii aadan 30 daqiiqo gudahood ku bixin, dalabku wuu baaqanayaa.</i>\n"
            "Sawirka rasiidka <b>(Screenshot)</b> halkan soo dir:"
        ),
        'pay_instruct_sell': (
            "⏳ <b>Waqtiga 30 daqiiqo waa bilowday!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🌐 <b>TRC20 Wallet Address:</b> <code>{wallet}</code>\n"
            "💎 <b>Qadarka aad direysid:</b> <code>{usd:,.2f} USDT</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>Haddii aadan 30 daqiiqo gudahood dirin, dalabku wuu baaqanayaa.</i>\n"
            "Dirista kadib sawirka <b>(Screenshot)</b> halkan soo dir:"
        ),
        'got_ss_buy': "✅ <b>Rasiidkii waa la helay! AI ayaa xaqiijinaya...</b>\n\n🎯 Hadda soo dir <b>TRC20 Address ama Binance Pay ID</b>:",
        'got_ss_sell': "✅ <b>Rasiidkii waa la helay! AI ayaa xaqiijinaya...</b>\n\n📱 Hadda soo dir <b>Nambarkaaga Telebirr iyo Magacaaga</b>:",
        'complete': "🎉 <b>Dalabkaaga si guul leh ayaa loo diray!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n⏳ Admin ayaa hubinaya. Waad mahadsan tahay!",
        'support_prompt': "💬 <b>Xarunta Caawimada</b>\n━━━━━━━━━━━━━━━━━━━━━━\nFadlan halkaan ku qor su'aashaada.",
        'support_sent': "✅ Farriintaadii waxaa loo diray Admin!",
        'btn_cancel': "❌ Jooji (Cancel)",
        'btn_support': "💬 Caawimo (Support)"
    }
}

def get_txt(context: ContextTypes.DEFAULT_TYPE) -> dict:
    lang = context.user_data.get('lang', 'am')
    return TEXTS.get(lang, TEXTS['am'])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    user = update.effective_user
    if user:
        record_user(user.id, user.username or "NoUsername")

    keyboard = [
        [
            InlineKeyboardButton("🇪🇹 Amharic", callback_data="lang_am"),
            InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_om")
        ],
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇸🇴 Somali", callback_data="lang_so")
        ]
    ]
    if update.message:
        await update.message.reply_text(
            "🌐 <b>Select Language / ቋንቋ ይምረጡ / Lugha Filadhaa / Dooro Luqadda:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        await update.message.reply_text(
            "💡 <i>Main Menu / ቋንቋ መቀየሪያ</i>",
            reply_markup=PERMANENT_KEYBOARD,
            parse_mode="HTML"
        )
    return LANG

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        lang_code = query.data.split("_")[1]
        context.user_data['lang'] = lang_code
        txt = get_txt(context)
        rate = db_get_rate()
        
        webapp_url = os.environ.get("WEB_APP_URL", "https://google.com")
        
        keyboard = [
            [InlineKeyboardButton(txt['buy_btn'], callback_data="trade_buy"), InlineKeyboardButton(txt['sell_btn'], callback_data="trade_sell")],
            [InlineKeyboardButton(txt['webapp_btn'], web_app=WebAppInfo(url=webapp_url))],
            [InlineKeyboardButton(txt['btn_support'], callback_data="bot_support")]
        ]
        await query.message.edit_text(txt['welcome'].format(rate=rate), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
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

async def handle_support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        user = update.effective_user
        txt = get_txt(context)
        if user:
            admin_msg = (
                f"📩 <b>NEW SUPPORT MESSAGE!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>From:</b> @{user.username} (<code>{user.id}</code>)\n"
                f"📝 <b>Message:</b> {update.message.text}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            admin_btn = [[InlineKeyboardButton("💬 Reply to User", callback_data=f"reply_{user.id}")] ]
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(admin_btn), parse_mode="HTML")
        await update.message.reply_text(txt['support_sent'], parse_mode="HTML")
        context.user_data.clear()
        return ConversationHandler.END
    return SUPPORT_MSG

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
        trade_type = context.user_data.get('trade_type', 'buy')

        keyboard = [
            [InlineKeyboardButton("✅ Proceed / አረጋግጥ", callback_data="proceed_pay")],
            [InlineKeyboardButton(txt['btn_cancel'], callback_data="user_cancel")]
        ]
        
        if trade_type == 'buy':
            msg = txt['summary_buy'].format(usd=usd_amount, rate=rate, birr=total_birr)
        else:
            msg = txt['summary_sell'].format(usd=usd_amount, rate=rate, birr=total_birr)
            
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return PAYMENT_CHOICE

    except ValueError:
        await update.message.reply_text(txt['invalid_num'].format(min=MIN_USD, max=MAX_USD), parse_mode="HTML")
        return AMOUNT

async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        txt = get_txt(context)
        trade_type = context.user_data.get('trade_type', 'buy')
        total_birr = context.user_data.get('total_birr', 0)
        usd_amount = context.user_data.get('usd_amount', 0)

        keyboard = [[InlineKeyboardButton(txt['btn_cancel'], callback_data="user_cancel")]]

        if trade_type == 'buy':
            msg = txt['pay_instruct_buy'].format(birr=total_birr, num=PAYMENT_NUMBER, name=ADMIN_NAME)
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
        
        photo_file_obj = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file_obj.download_as_bytearray()
        
        expected_birr = context.user_data.get('total_birr', 0.0)
        _, ai_status_text = await verify_screenshot_ai(photo_bytes, expected_birr)
        context.user_data['ai_status'] = ai_status_text

        await update.message.reply_text(txt['got_ss_buy'], parse_mode="HTML")
        return WALLET_ADDRESS
    return SCREENSHOT

async def receive_sell_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = get_txt(context)
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        context.user_data['photo_file'] = photo.file_id
        
        photo_file_obj = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file_obj.download_as_bytearray()
        
        expected_usd = context.user_data.get('usd_amount', 0.0)
        _, ai_status_text = await verify_screenshot_ai(photo_bytes, expected_usd)
        context.user_data['ai_status'] = ai_status_text

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
        ai_status = context.user_data.get('ai_status', 'No AI Audit Data')

        if user:
            record_order(user.id, "BUY", usd, birr)

            admin_msg = (
                f"🚨 <b>NEW BUY ORDER RECEIVED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> @{user.username} (<code>{user.id}</code>)\n"
                f"💎 <b>Amount:</b> <code>{usd:,.2f} USDT</code>\n"
                f"💰 <b>Total Birr:</b> <code>{birr:,.2f} ETB</code>\n"
                f"📱 <b>Payment Method:</b> <code>Telebirr</code>\n"
                f"📍 <b>Payout Wallet:</b> <code>{wallet}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <b>AI Audit Report:</b>\n{ai_status}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            admin_btn = [
                [InlineKeyboardButton("📸 Send Payment Proof", callback_data=f"proof_{user.id}")],
                [InlineKeyboardButton("✅ Quick Approve", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")],
                [InlineKeyboardButton("💬 Message User", callback_data=f"reply_{user.id}")]
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
        ai_status = context.user_data.get('ai_status', 'No AI Audit Data')

        if user:
            record_order(user.id, "SELL", usd, birr)

            admin_msg = (
                f"🚨 <b>NEW SELL ORDER RECEIVED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> @{user.username} (<code>{user.id}</code>)\n"
                f"💎 <b>Amount:</b> <code>{usd:,.2f} USDT</code>\n"
                f"💰 <b>Total Birr:</b> <code>{birr:,.2f} ETB</code>\n"
                f"📱 <b>Payout Telebirr:</b> <code>{telebirr_info}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <b>AI Audit Report:</b>\n{ai_status}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            admin_btn = [
                [InlineKeyboardButton("📸 Send Payment Proof", callback_data=f"proof_{user.id}")],
                [InlineKeyboardButton("✅ Quick Approve", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")],
                [InlineKeyboardButton("💬 Message User", callback_data=f"reply_{user.id}")]
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

        if action == "proof":
            context.bot_data['proof_target_id'] = target_user_id
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📸 <b>Send payment proof screenshot for User ID <code>{target_user_id}</code>:</b>",
                parse_mode="HTML"
            )
        elif action == "approve":
            await context.bot.send_message(chat_id=target_user_id, text="🎉 <b>Your order has been successfully approved! Thank you!</b>", parse_mode="HTML")
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n✅ <b>STATUS: APPROVED</b>", parse_mode="HTML")
        elif action == "reject":
            await context.bot.send_message(chat_id=target_user_id, text="❌ <b>Your order has been rejected. Please contact support.</b>", parse_mode="HTML")
            await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n❌ <b>STATUS: REJECTED</b>", parse_mode="HTML")
        elif action == "reply":
            context.bot_data['reply_target_id'] = target_user_id
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"✍️ <b>Type your message to User ID <code>{target_user_id}</code>:</b>",
                parse_mode="HTML"
            )

async def admin_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    Info = update.message
    if not Info or not Info.from_user or Info.from_user.id != ADMIN_ID:
        return

    proof_target_id = context.bot_data.get('proof_target_id')
    if proof_target_id and Info.photo:
        photo_id = Info.photo[-1].file_id
        caption_text = (
            "🎉 <b>ORDER COMPLETED SUCCESSFULLY!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🧾 <b>Payment Proof attached above.</b>\n"
            "Thank you for trading with us! 🙏"
        )
        await context.bot.send_photo(chat_id=proof_target_id, photo=photo_id, caption=caption_text, parse_mode="HTML")
        await Info.reply_text(f"✅ Payment proof sent to User ID <code>{proof_target_id}</code>!", parse_mode="HTML")
        context.bot_data.pop('proof_target_id', None)
        return

    reply_target_id = context.bot_data.get('reply_target_id')
    if reply_target_id and Info.text:
        reply_text = Info.text
        await context.bot.send_message(
            chat_id=reply_target_id,
            text=f"💬 <b>Admin Message:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n{reply_text}",
            parse_mode="HTML"
        )
        await Info.reply_text(f"✅ Message sent to User ID <code>{reply_target_id}</code>!", parse_mode="HTML")
        context.bot_data.pop('reply_target_id', None)

async def cancel_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text("❌ <b>Order cancelled. Send /start to restart.</b>", parse_mode="HTML")
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    if not BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN missing.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    restart_handler = MessageHandler(filters.Regex("^🔄 Main Menu"), start)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), restart_handler],
        states={
            LANG: [CallbackQueryHandler(select_language, pattern="^lang_")],
            TRADE_TYPE: [CallbackQueryHandler(select_trade_type, pattern="^(trade_|bot_support)")],
            SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), handle_support_msg)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), get_amount)],
            PAYMENT_CHOICE: [CallbackQueryHandler(payment_selected, pattern="^proceed_pay$")],
            SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
            WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), receive_wallet)],
            SELL_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_sell_screenshot)],
            SELL_TELEBIRR: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^🔄 Main Menu"), receive_sell_telebirr)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_button_handler, pattern="^user_cancel$"),
            restart_handler,
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_decision_handler, pattern="^(proof_|approve_|reject_|reply_)"))
    app.add_handler(MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), admin_media_handler))

    logger.info("Buna Bonus P2P Bot running with WebApp and Multi-language Support...")
    app.run_polling()

if __name__ == "__main__":
    main()
