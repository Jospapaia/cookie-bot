import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOTAL_COOKIES = 60
COOKIE_COUNTER_FILE = "cookie_count.txt"
ORDERS_FILE = "orders.txt"
ANNOUNCE_CHAT_ID = os.getenv("ANNOUNCE_CHAT_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def get_remaining_cookies():
    if not os.path.exists(COOKIE_COUNTER_FILE):
        with open(COOKIE_COUNTER_FILE, "w") as f:
            f.write(str(TOTAL_COOKIES))
        return TOTAL_COOKIES
    with open(COOKIE_COUNTER_FILE, "r") as f:
        return int(f.read())

def update_remaining_cookies(new_value):
    with open(COOKIE_COUNTER_FILE, "w") as f:
        f.write(str(new_value))

def get_existing_order_count(user_id):
    if not os.path.exists(ORDERS_FILE):
        return 0
    with open(ORDERS_FILE, "r") as f:
        for line in f:
            if line.startswith(f"{user_id},"):
                parts = line.strip().split(",")
                if len(parts) == 4:
                    return int(parts[3])
    return 0

def record_order(user_id, username, first_name, count):
    lines = []
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            lines = f.readlines()

    updated = False
    with open(ORDERS_FILE, "w") as f:
        for line in lines:
            if line.startswith(f"{user_id},"):
                f.write(f"{user_id},{username},{first_name},{count}\n")
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f"{user_id},{username},{first_name},{count}\n")

def delete_order(user_id):
    lines = []
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            lines = f.readlines()

    remaining_cookies_to_add = 0
    with open(ORDERS_FILE, "w") as f:
        for line in lines:
            if line.startswith(f"{user_id},"):
                parts = line.strip().split(",")
                if len(parts) == 4:
                    remaining_cookies_to_add += int(parts[3])
                continue  # skip writing this line
            f.write(line)

    return remaining_cookies_to_add

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remaining = get_remaining_cookies()
    await update.message.reply_text(
        f"🍪 יש {remaining} עוגיות זמינות להזמנה.\n"
        f"תשלחו לי מספר (למשל 2) וארשום אתכם.\n"
        f"🮡 האיסוף מרחוב המייסדים 3 – נא להגיע עם קופסה."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("שלחו לי רק מספר (למשל: 2)")
        return

    requested = int(text)
    user = update.effective_user
    existing_order = get_existing_order_count(user.id)
    delta = requested - existing_order

    remaining = get_remaining_cookies()

    if delta > remaining:
        await update.message.reply_text(f"יש רק {remaining} עוגיות זמינות כרגע.")
    else:
        update_remaining_cookies(remaining - delta)
        record_order(user.id, user.username or "", user.first_name or "", requested)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ סיימתי", callback_data="done")]
        ])
        
        new_remaining = remaining - delta
        
        await update.message.reply_text(
            f"🎉 נרשמת! העוגיות מוכנות לאיסוף מרחוב המייסדים 3, קומה 1, משפחת שמש 🌞\n"
            f"ניתן לעדכן את הכמות בשליחת מספר חדש.\n"
            f"לאחר איסוף העוגיות, נא ללחוץ על הכפתור למטה:",
            reply_markup=keyboard
        )

        if new_remaining == 0 and ANNOUNCE_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=int(ANNOUNCE_CHAT_ID),
                    text="❌ העוגיות נגמרו!\nאני מקווה לעדכן בקרוב על עוגיות טריות 🧈🍪"
                )
            except Exception as e:
                logging.error(f"שגיאה בשליחת הודעת סיום: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "done":
        user = query.from_user
        returned = delete_order(user.id)
        
        await query.edit_message_text(
            f"✅ תודה על האיסוף, מקווה שתהנו ושהנחמה תהיה מתוקה"
        )

async def new_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ הפקודה הזו זמינה רק למפעיל הבוט.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("שלח פקודה בפורמט: /newbatch 60")
        return

    new_total = int(context.args[0])
    update_remaining_cookies(new_total)

    if os.path.exists(ORDERS_FILE):
        os.remove(ORDERS_FILE)

    try:
        await update.message.delete()
    except Exception as e:
        logging.warning(f"שגיאה במחיקת הודעת /newbatch: {e}")

    msg = (
        "🍪 *יש עוגיות טריות!*\n"
        f"עכשיו זמינות להזמנה – הבוט מחכה לכם {new_total} 🍪\n\n"
        "🮡 האיסוף מרחוב המייסדים 3 – נא להגיע עם קופסה.\n\n"
        "📲 להזמנה – דרך הבוט:\n"
        "https://t.me/YossisCookiesForTheSoulBot?start=start\n\n"
        "🙏 אנא הזמינו כמות שמתאימה למשפחה שלכם – כדי שיישאר לכולם."
    )

    try:
        if ANNOUNCE_CHAT_ID:
            await context.bot.send_message(chat_id=int(ANNOUNCE_CHAT_ID), text=msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"שגיאה בשליחת הודעה לקבוצה: {e}")

async def export_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ הפקודה הזו זמינה רק למפעיל הבוט.")
        return

    if not os.path.exists(ORDERS_FILE):
        await update.message.reply_text("אין הזמנות כרגע.")
        return

    lines = []
    with open(ORDERS_FILE, "r") as f:
        for line in f:
            user_id, username, first_name, count = line.strip().split(",")
            display = f"[{first_name}](tg://user?id={user_id})" if not username else f"[@{username}](https://t.me/{username})"
            lines.append(f"{display} – {count} עוגיות")

    report = "\n".join(lines) or "אין הזמנות כרגע."
    await update.message.reply_text(report, parse_mode="Markdown")
    
if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newbatch", new_batch))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("export", export_orders))
    
    print("🤖 הבוט פועל...")
    app.run_polling()
