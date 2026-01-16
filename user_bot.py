
import asyncio
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from database import Database
from config import ADMIN_IDS, USER_BOT_TOKEN, ADMIN_BOT_TOKEN
from strings import STRINGS

db = Database()

# Conversation States
WAIT_INPUT = range(1)
REDEEM_CODE = range(1)

# --- Helpers ---
async def get_lang(user_id):
    user = await db.get_user(user_id)
    if user and user[8]: 
        return user[8]
    return 'en' 

async def notify_admins_start(app, message):
    admin_bot = Bot(ADMIN_BOT_TOKEN)
    for admin_id in ADMIN_IDS:
        try: await admin_bot.send_message(chat_id=admin_id, text=message)
        except: pass

async def notify_admin_order(app, text, order_payload=None):
    admin_bot = Bot(ADMIN_BOT_TOKEN)
    for admin_id in ADMIN_IDS:
        try: await admin_bot.send_message(chat_id=admin_id, text=text)
        except: pass

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = None
    
    if args and args[0].isdigit():
        possible_referrer = int(args[0])
        if possible_referrer != user.id:
            referrer_id = possible_referrer

    is_new = await db.add_user(user.id, user.first_name, user.username, referrer_id)
    
    if is_new:
        await db.set_language(user.id, 'en') 
        await notify_admins_start(context.application, f"🔔 **New Member Joined**\nName: {user.first_name}\nID: `{user.id}`\nUsername: @{user.username or 'None'}\nReferrer: `{referrer_id}`")
        if referrer_id:
            ref_user = await db.get_user(referrer_id)
            if ref_user:
                bonus = await db.get_setting('ref_bonus')
                amount = int(bonus) if bonus else 10
                await db.add_referral_reward(referrer_id, amount)
                try:
                    msg = f"🎉 New Referral! You earned {amount} TK."
                    await context.bot.send_message(chat_id=referrer_id, text=msg)
                except: pass

    await main_menu(update, context)

async def set_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: msg = update.callback_query.message
    else: msg = update.message
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"), InlineKeyboardButton("🇵🇰 اردو", callback_data="lang_ur")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
    ]
    text = STRINGS['en']['choose_lang']
    if update.callback_query: await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    await db.set_language(query.from_user.id, lang)
    await main_menu(update, context)

# --- Revamped Main Menu ---
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_lang(user_id)
    if lang not in STRINGS: lang = 'en'
    s = STRINGS[lang]
    
    # New Layout:
    # [Daily Check]
    # [Shop] [Profile]
    # [Redeem] [Refer]
    # [Add Balance] [Support]
    
    keyboard = [
        [InlineKeyboardButton(s['btn_daily'], callback_data="daily_check")],
        [InlineKeyboardButton(s['btn_shop'], callback_data="menu_shop"), 
         InlineKeyboardButton(s['btn_profile'], callback_data="menu_profile")],
        [InlineKeyboardButton(s['btn_redeem_main'], callback_data="redeem_start"),
         InlineKeyboardButton(s['btn_refer'], callback_data="menu_refer")],
        [InlineKeyboardButton(s['btn_add_balance'], callback_data="menu_balance"), 
         InlineKeyboardButton(s['btn_support'], url="https://t.me/developermunna")],
        [InlineKeyboardButton("🌐 Language", callback_data="menu_lang")]
    ]
    text = s['welcome']
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- Daily Check Logic ---
async def daily_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    user = await db.get_user(user_id)
    # user[9] is last_daily_check
    last_check = user[9]
    
    now = datetime.datetime.now()
    can_claim = False
    
    if not last_check:
        can_claim = True
    else:
        # Check if last_check was a different day (simple logic: compare date strings)
        # last_check comes as string from SQLite usually, unless parsed.
        # aiosqlite returns raw strings/ints mostly.
        # Assuming format 'YYYY-MM-DD HH:MM:SS...'
        if isinstance(last_check, str):
            try:
                last_date = datetime.datetime.strptime(last_check.split('.')[0], '%Y-%m-%d %H:%M:%S').date()
            except:
                last_date = None # Should not happen if format consistent
        else:
             last_date = last_check.date() if last_check else None

        if last_date != now.date():
            can_claim = True

    if can_claim:
        await db.update_balance(user_id, 10, add=True)
        await db.update_daily_check(user_id)
        await query.answer(STRINGS[lang]['daily_success'], show_alert=True)
    else:
        await query.answer(STRINGS[lang]['daily_fail'], show_alert=True)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    user = await db.get_user(user_id)
    stats = STRINGS[lang]['profile_stats'].format(user[0], user[3], user[5], user[6])
    await query.edit_message_text(stats, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]]))

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    bot_username = context.bot.username
    link = f"https://t.me/{bot_username}?start={user_id}"
    bonus = await db.get_setting('ref_bonus')
    amount = bonus if bonus else "10"
    text = f"👥 **Referral System**\n\nShare your link and earn {amount} TK per user!\n\nLink:\n`{link}`"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]]))

async def balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    # Add Balance -> Coming Soon
    # Only offer this alert
    await query.answer(STRINGS[lang]['coming_soon'], show_alert=True)
    # Don't change screen

# --- Redeem Logic ---
async def start_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🎁 Enter your **Redeem Code**:", parse_mode='Markdown')
    return REDEEM_CODE

async def process_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    res = await db.use_redeem_code(code, update.effective_user.id)
    
    if res == "invalid":
        await update.message.reply_text("❌ Invalid Code.")
    elif res == "exhausted":
        await update.message.reply_text("❌ Code limit reached.")
    elif res == "already_used":
        await update.message.reply_text("❌ You have already redeemed this code.")
    else:
        # Success
        await update.message.reply_text(f"✅ Success! Added {res} TK to your wallet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="menu_main")]]))
    
    return ConversationHandler.END

# --- Shop Logic (Updated UI) ---
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    s = STRINGS[lang]
    services = await db.get_services()
    if not services:
        await query.answer(s['shop_empty'], show_alert=True)
        return

    keyboard = []
    for svc in services:
        stock_msg = ""
        if svc['type'] == 'auto':
            count = await db.get_stock_count(svc['id'])
            stock_msg = f"({count} in stock)"
            if count == 0: stock_msg = "(❌ Stock Out)"
        
        # Format: Name | Price TK (Stock)
        btn_text = f"{svc['name']} | {svc['price']} TK {stock_msg}"
        
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"buy_{svc['id']}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_main")])
    await query.edit_message_text(s['btn_shop'], reply_markup=InlineKeyboardMarkup(keyboard))

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_lang(user_id)
    service_id = int(query.data.split("_")[1])
    
    service = await db.get_service(service_id)
    if not service:
        await query.answer("Service not found", show_alert=True)
        return

    user = await db.get_user(user_id)
    if user[3] < service['price']:
        await query.answer(STRINGS[lang]['insufficient_balance'], show_alert=True)
        return

    if service['type'] == 'auto':
        count = await db.get_stock_count(service_id)
        if count == 0:
            await query.answer(STRINGS[lang]['out_of_stock'], show_alert=True)
            return

    text = STRINGS[lang]['confirm_buy'].format(service['name'], service['price'])
    context.user_data['buy_service'] = service
    
    keyboard = [
        [InlineKeyboardButton(STRINGS[lang]['btn_confirm'], callback_data="confirm_buy_yes"),
         InlineKeyboardButton(STRINGS[lang]['btn_cancel'], callback_data="menu_shop")]
    ]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_buy_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    service = context.user_data.get('buy_service')
    if not service:
        await main_menu(update, context)
        return ConversationHandler.END

    if service.get('question'):
        # Need Input
        await query.edit_message_text(f"📝 **Requirement**\n\n{service['question']}\n\nPlease reply with the information:", parse_mode='Markdown')
        return WAIT_INPUT
    else:
        # Proceed standard
        await finalize_order(update, context, service, None)
        return ConversationHandler.END

async def receive_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    service = context.user_data.get('buy_service')
    await finalize_order(update, context, service, user_input)
    return ConversationHandler.END

async def finalize_order(update: Update, context: ContextTypes.DEFAULT_TYPE, service, user_input):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        msg_method = update.callback_query.edit_message_text
    else:
        user_id = update.effective_user.id
        msg_method = update.message.reply_text

    lang = await get_lang(user_id)
    
    user = await db.get_user(user_id)
    if user[3] < service['price']:
        await msg_method(STRINGS[lang]['insufficient_balance'])
        return

    content_deliver = ""
    order_status = "completed"
    
    if service['type'] == 'auto':
        content_deliver = await db.fetch_stock_item(service['id'])
        if not content_deliver:
             await msg_method("Stock ran out!")
             return
    else:
        content_deliver = "Manual Delivery Pending"
        order_status = "pending"

    await db.update_balance(user_id, service['price'], add=False)
    await db.log_order(user_id, service['id'], content_deliver, service['price'], status=order_status, user_input=user_input)
    
    if service['type'] == 'auto':
        msg = STRINGS[lang]['order_success'].format(content_deliver)
        await msg_method(msg)
        await notify_admin_order(context.application, f"⚡ **Auto Service Sold**\nUser: `{user_id}`\nService: {service['name']}\nPrice: {service['price']}")
    else:
        msg = STRINGS[lang]['order_manual']
        await msg_method(msg)
        
        admin_text = f"🛒 **New Order Request**\nUser: `{user_id}`\nService: {service['name']}\nPrice: {service['price']}"
        if user_input: admin_text += f"\n\n📝 **User Input**: `{user_input}`"
        await notify_admin_order(context.application, admin_text)

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)
    return ConversationHandler.END

def setup_user_bot(application):
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_buy_choice, pattern="^confirm_buy_yes")],
        states={WAIT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_input)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_message=False
    )
    
    redeem_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_redeem, pattern="^redeem_start")],
        states={REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_redeem)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_message=False
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(set_language_menu, pattern="^menu_lang"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^menu_main"))
    application.add_handler(CallbackQueryHandler(shop, pattern="^menu_shop"))
    application.add_handler(CallbackQueryHandler(profile, pattern="^menu_profile"))
    application.add_handler(CallbackQueryHandler(refer, pattern="^menu_refer"))
    application.add_handler(CallbackQueryHandler(buy_confirm, pattern="^buy_"))
    application.add_handler(buy_conv)
    application.add_handler(CallbackQueryHandler(balance_menu, pattern="^menu_balance"))
    application.add_handler(CallbackQueryHandler(daily_check, pattern="^daily_check")) # New Handler
    application.add_handler(redeem_conv)
    # application.add_handler(CallbackQueryHandler(main_menu, pattern="^menu_support")) # Support is URL now
