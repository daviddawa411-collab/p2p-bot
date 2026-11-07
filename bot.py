import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Logging ማስተካከል
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# የቦት እና አድሚን መረጃዎች
TOKEN = "8477592504:AAGjyhk0EPH4TTZ6pAb3o7M6obgTA15V5Z4"
ADMIN_ID = 7798227927

# ደንቦች እና አድራሻዎች
MIN_USDT = 15.0
MAX_USDT = 600.0
RATE_ETB = 190.0

# User states storage
USER_STATES = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("🌐 አማርኛ (Amharic)", callback_data="lang_am"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🌳 Oromiffa", callback_data="lang_or"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Waa gwaan {user.first_name}! 🫡\n\nእባክዎን ቋንቋ ይምረጡ / Please select your language / Afaan filadhaa:",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # 1. ቋንቋ ሲመረጥ
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        USER_STATES[user_id] = {"lang": lang}

        if lang == "am":
            text = (
                f"እንኳን ወደ **BIRRBOUNSP2P** በደህና መጡ! 💸\n\n"
                f"📌 **የመግዣ ደንብ:**\n"
                f"▪️ አነስተኛ መጠን (Min): **15 USDT**\n"
                f"▪️ ከፍተኛ መጠን (Max): **600 USDT**\n"
                f"▪️ የምንዛሬ መጠን: **1 USDT = 190 ETB**\n\n"
                f"እባክዎን መግዛት የሚፈልጉትን የ USDT መጠን ያስገቡ (ለምሳሌ: 15, 50, 100):"
            )
        elif lang == "or":
            text = (
                f"Baga nagaan gara **BIRRBOUNSP2P** dhuftan! 💸\n\n"
                f"📌 **Seera Bituu:**\n"
                f"▪️ Xiqqaa (Min): **15 USDT**\n"
                f"▪️ Guddaa (Max): **600 USDT**\n"
                f"▪️ Gatiin: **1 USDT = 190 ETB**\n\n"
                f"Mee hamma USDT bituu barbaaddan galchaa (fakkeenyaaf: 15, 50, 100):"
            )
        else:
            text = (
                f"Welcome to **BIRRBOUNSP2P**! 💸\n\n"
                f"📌 **Buying Rules:**\n"
                f"▪️ Minimum Order: **15 USDT**\n"
                f"▪️ Maximum Order: **600 USDT**\n"
                f"▪️ Rate: **1 USDT = 190 ETB**\n\n"
                f"Please enter the USDT amount you want to buy (e.g., 15, 50, 100):"
            )

        USER_STATES[user_id]["state"] = "AWAITING_AMOUNT"
        await query.edit_message_text(text=text, parse_mode="Markdown")

    # 2. ተጠቃሚው የሚቀበልበትን መንገድ (TRC20 ወይም Mastercard) ሲመርጥ
    elif data.startswith("recv_"):
        recv_method = data.split("_")[1]
        USER_STATES[user_id]["recv_method"] = recv_method
        USER_STATES[user_id]["state"] = "AWAITING_WALLET_INFO"

        lang = USER_STATES[user_id].get("lang", "am")
        if recv_method == "trc20":
            msg = (
                "✍️ እባክዎን የ **USDT TRC20 ዋሌት አድራሻዎን** (Wallet Address) ይጻፉልን:"
                if lang == "am"
                else "✍️ Please enter your **USDT TRC20 Wallet Address**:"
            )
        else:
            msg = (
                "✍️ እባክዎን የ **Mastercard** መረጃዎን (የካርድ ቁጥር እና ስም) ይጻፉልን:"
                if lang == "am"
                else "✍️ Please enter your **Mastercard** details (Card number and Name):"
            )

        await query.edit_message_text(text=msg, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    state_data = USER_STATES.get(user_id, {})
    lang = state_data.get("lang", "am")
    current_state = state_data.get("state")

    # 1. መጠን (Amount) መቀበል
    if current_state == "AWAITING_AMOUNT" and update.message.text:
        try:
            amount = float(update.message.text)

            if amount < MIN_USDT:
                msg = (
                    f"❌ አነስተኛ መግዣ መጠን **{MIN_USDT} USDT** ነው።"
                    if lang == "am"
                    else f"❌ Minimum order is **{MIN_USDT} USDT**."
                )
                await update.message.reply_text(msg, parse_mode="Markdown")
                return

            if amount > MAX_USDT:
                msg = (
                    f"❌ የዕለት ከፍተኛው ገደብ **{MAX_USDT} USDT** ነው።"
                    if lang == "am"
                    else f"❌ Daily maximum limit is **{MAX_USDT} USDT**."
                )
                await update.message.reply_text(msg, parse_mode="Markdown")
                return

            total_etb = amount * RATE_ETB
            USER_STATES[user_id]["amount"] = amount
            USER_STATES[user_id]["total_etb"] = total_etb
            USER_STATES[user_id]["state"] = "AWAITING_PAYMENT_SCREENSHOT"

            if lang == "am":
                payment_text = (
                    f"✅ **የክፍያ ማጠቃለያ:**\n\n"
                    f"💵 የሚገዙት: **{amount:.2f} USDT**\n"
                    f"🧮 የሚከፍሉት: **{total_etb:,.2f} ETB** (በ 190 Birr rate)\n\n"
                    f"📲 **የTelebirr ክፍያ መረጃ:**\n"
                    f"▪️ ስም: **BEREKET**\n"
                    f"▪️ ስልክ: `0900253321`\n\n"
                    f"⚠️ እባክዎን ክፍያውን ከፈጸሙ በኋላ የትራንስፈር **Screenshot (ፎቶ)** እዚህ ይላኩ!"
                )
            else:
                payment_text = (
                    f"✅ **Payment Summary:**\n\n"
                    f"💵 You get: **{amount:.2f} USDT**\n"
                    f"🧮 Total: **{total_etb:,.2f} ETB** (Rate: 190 Birr)\n\n"
                    f"📲 **Telebirr Payment Info:**\n"
                    f"▪️ Name: **BEREKET**\n"
                    f"▪️ Phone: `0900253321`\n\n"
                    f"⚠️ After paying, please upload your transfer **Screenshot** here!"
                )

            await update.message.reply_text(payment_text, parse_mode="Markdown")

        except ValueError:
            msg = (
                "እባክዎን ትክክለኛ ቁጥር ያስገቡ!"
                if lang == "am"
                else "Please enter a valid number!"
            )
            await update.message.reply_text(msg)

    # 2. የብር ክፍያ Screenshot ሲላክ
    elif current_state == "AWAITING_PAYMENT_SCREENSHOT" and update.message.photo:
        photo_file = update.message.photo[-1].file_id
        USER_STATES[user_id]["payment_photo"] = photo_file
        USER_STATES[user_id]["state"] = "CHOOSE_RECEIVE_METHOD"

        # ተጠቃሚው USDT የሚቀበልበትን መንገድ እንዲመርጥ ቁልፎችን ማሳየት
        keyboard = [
            [
                InlineKeyboardButton(
                    "🪙 USDT (TRC20)", callback_data="recv_trc20"
                ),
                InlineKeyboardButton(
                    "💳 Mastercard", callback_data="recv_mastercard"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = (
            "✅ የክፍያ Screenshot ደርሶናል!\n\n👇 አሁን <u>USDT የሚቀበሉበትን መንገድ</u> ይምረጡ:"
            if lang == "am"
            else "✅ Payment screenshot received!\n\n👇 Now select your <u>receiving method</u>:"
        )

        await update.message.reply_text(
            msg, reply_markup=reply_markup, parse_mode="Markdown"
        )

    # 3. ተጠቃሚው የዋሌት አድራሻውን ወይም የካርድ መረጃውን ሲጽፍ (ለአድሚን የመጨረሻ መረጃ ማስተላለፍ)
    elif current_state == "AWAITING_WALLET_INFO" and update.message.text:
        wallet_info = update.message.text
        amount = state_data.get("amount")
        total_etb = state_data.get("total_etb")
        recv_method = state_data.get("recv_method", "N/A").upper()
        payment_photo = state_data.get("payment_photo")

        # ለአድሚን የሚላኩ ሙሉ መረጃዎች
        admin_msg = (
            f"🚨 **አዲስ የተጠናቀቀ P2P ትዕዛዝ (BIRRBOUNSP2P)!**\n\n"
            f"👤 ተጠቃሚ: {user.first_name} (@{user.username})\n"
            f"🆔 ID: `{user_id}`\n"
            f"💵 መጠን: **{amount} USDT**\n"
            f"💰 የተከፈለ ብር: **{total_etb:,.2f} ETB**\n"
            f"📥 የመቀበያ መንገድ: **{recv_method}**\n"
            f"📌 የመቀበያ አድራሻ/መረጃ:\n`{wallet_info}`"
        )

        try:
            # ፎቶውን ከሙሉ መረጃው ጋር ለአድሚን መላክ
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=payment_photo,
                caption=admin_msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send to admin: {e}")

        # ለተጠቃሚው ማረጋገጫ መስጠት
        if lang == "am":
            confirm_msg = f"🎉 ትዕዛዝዎ በትክክል ተመዝግቦ ለአድሚን ተልኳል!\n\nየከፈሉትን ብር አረጋግጠን በ **{recv_method}** አማካኝነት የጠየቁትን **{amount} USDT** ገቢ እናደርግልዎታለን። እናመሰግናለን!"
        else:
            confirm_msg = f"🎉 Your order has been successfully submitted to Admin!\n\nWe will verify your payment and send **{amount} USDT** via **{recv_method}**. Thank you!"

        await update.message.reply_text(confirm_msg)
        USER_STATES[user_id]["state"] = "COMPLETED"


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT | filters.PHOTO, handle_message)
    )

    print("BIRRBOUNSP2P Bot is running smoothly...")
    app.run_polling()


if __name__ == "__main__":
    main()
