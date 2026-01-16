
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from database import Database
from config import ADMIN_IDS, ADMIN_BOT_TOKEN, USER_BOT_TOKEN

db = Database()

# States
ADD_SVC_NAME, ADD_SVC_PRICE, ADD_SVC_TYPE, ADD_SVC_QUESTION = range(4)
ADD_STOCK_SVC, ADD_STOCK_CONTENT = range(2)
BROADCAST_MSG = range(1)
SETTINGS_REF_BONUS = range(1)
ADD_CODE_VAL, ADD_CODE_USES = range(2)

# --- Helpers ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data.clear()
    
    pending = await db.get_pending_orders()
    pending_text = f"⏳ Pending ({len(pending)})" if pending else "⏳ Pending Orders"
    
    text = "👑 **Admin Panel**\nSelect an action:"
    keyboard = [
        [InlineKeyboardButton("➕ Add Service", callback_data="admin_add_svc"),
         InlineKeyboardButton("📋 Services", callback_data="admin_list_svc")],
        [InlineKeyboardButton("📦 Add Stock", callback_data="admin_add_stock"),
         InlineKeyboardButton("💰 Pay/Deduct", callback_data="admin_pay")],
        [InlineKeyboardButton(pending_text, callback_data="admin_pending"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
         InlineKeyboardButton("🎁 Codes", callback_data="admin_codes")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")]
    ]
    
    if update.callback_query:
        try: await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        except: await update.callback_query.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    await admin_start(update, context)

# --- Add Service Flow (Refined) ---
async def start_add_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    await update.effective_message.reply_text("🆕 **Add New Service**\n\nEnter Service Name:", parse_mode='Markdown')
    return ADD_SVC_NAME

async def add_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['svc_name'] = update.message.text
    await update.message.reply_text("Enter Price (TK):")
    return ADD_SVC_PRICE

async def add_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['svc_price'] = int(update.message.text)
        # Select Type with Buttons
        text = "Select Service Type:"
        keyboard = [
            [InlineKeyboardButton("⚡ Auto Delivery", callback_data="type_auto"),
             InlineKeyboardButton("🛠️ Manual Delivery", callback_data="type_manual")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_SVC_TYPE
    except:
        await update.message.reply_text("Invalid Number.")
        return ADD_SVC_PRICE

async def add_service_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    t = query.data.split("_")[1] # auto or manual
    context.user_data['svc_type'] = t
    
    if t == 'manual':
        # Enhanced Input Selection
        text = "Does this service require user input (e.g. Gmail/ID)?\n Select Option:"
        keyboard = [
            [InlineKeyboardButton("❌ No Input", callback_data="input_no")],
            [InlineKeyboardButton("📧 Require Gmail", callback_data="input_gmail")],
            [InlineKeyboardButton("🔢 Require Number/ID", callback_data="input_id")],
            [InlineKeyboardButton("📝 Custom Question...", callback_data="input_custom")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_SVC_QUESTION
    else:
        # Auto usually no input
        await finish_add_service(update, context, None)
        return ConversationHandler.END

async def add_service_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Could be button or text (custom)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "input_no":
            await finish_add_service(update, context, None)
        elif data == "input_gmail":
            await finish_add_service(update, context, "Please send your Gmail address:")
        elif data == "input_id":
            await finish_add_service(update, context, "Please send your Number or ID:")
        elif data == "input_custom":
             await query.edit_message_text("Type your custom question:")
             return ADD_SVC_QUESTION # Wait for text
    else:
        # Text input (Custom)
        q = update.message.text
        await finish_add_service(update, context, q)
    return ConversationHandler.END

async def finish_add_service(update, context, q):
    if update.callback_query: method = update.callback_query.message.reply_text
    else: method = update.message.reply_text
    
    await db.add_service(context.user_data['svc_name'], context.user_data['svc_price'], context.user_data['svc_type'], question=q)
    await method(f"✅ Service Added!\nType: {context.user_data['svc_type']}\nInput: {q or 'None'}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_home")]]))


# --- Other lists and handlers (Kept same) ---
async def list_pending_orders(update, context):
    query = update.callback_query
    orders = await db.get_pending_orders()
    if not orders:
        await query.answer("No Pending Orders!", show_alert=True)
        await admin_start(update, context)
        return
    text = "⏳ **Pending Orders**\nSelect an order:"
    keyboard = []
    for o in orders:
        btn_text = f"#{o['id']} U:{o['user_id']} - {o['service_name']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ord_view_{o['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_home")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def view_order(update, context):
    query = update.callback_query
    oid = int(query.data.split("_")[2])
    order = await db.get_order(oid)
    if not order or order['status'] != 'pending': 
        await query.answer("Invalid Order")
        await list_pending_orders(update, context)
        return
    u_input = order.get('user_input') or "None"
    text = (f"📦 **Order #{order['id']}**\n👤 User: `{order['user_id']}`\n🛍️ Service: {order.get('service_name')}\n💵 Price: {order['price']} TK\n📝 Input: `{u_input}`\n\nSelect Action:")
    keyboard = [[InlineKeyboardButton("✅ Mark Complete", callback_data=f"ord_act_complete_{oid}")], [InlineKeyboardButton("↩️ Refund", callback_data=f"ord_act_refund_{oid}")], [InlineKeyboardButton("⬅️ Back", callback_data="admin_pending")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def order_action(update, context):
    query = update.callback_query
    data = query.data.split("_")
    action, oid = data[2], int(data[3])
    order = await db.get_order(oid)
    if not order: return
    user_bot = Bot(USER_BOT_TOKEN)
    if action == "complete":
        await db.update_order_status(oid, 'completed')
        await query.answer("Completed")
        try: 
            print(f"DEBUG: Attempting to notify User {order['user_id']}")
            msg = f"✅ **Order Complete**\n\nYour account is active, you can check it now.\n\nService: {order['service_name']}"
            await user_bot.send_message(order['user_id'], msg) 
            print("DEBUG: Notification Sent Successfully")
        except Exception as e:
            print(f"DEBUG: Error sending msg to user: {e}")
    elif action == "refund":
        await db.update_order_status(oid, 'refunded')
        await db.update_balance(order['user_id'], order['price'], add=True)
        await query.answer("Refunded")
        try: await user_bot.send_message(order['user_id'], f"↩️ Order #{oid} Refunded.")
        except: pass
    await list_pending_orders(update, context)

async def list_services_btn(update, context):
    query = update.callback_query
    services = await db.get_services()
    if not services:
        await query.edit_message_text("No services.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_home")]]))
        return
    text = "📋 **Services List**\nClick to Delete:"
    keyboard = []
    for s in services:
        stock = await db.get_stock_count(s['id'])
        q_mark = "❓" if s.get('question') else ""
        btn_text = f"ID:{s['id']} {s['name']} ({s['price']}TK) [{stock}] {q_mark}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"svc_opt_{s['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_home")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def service_options(update, context):
    query = update.callback_query
    sid = int(query.data.split("_")[2])
    svc = await db.get_service(sid)
    if not svc:
        await list_services_btn(update, context)
        return
    text = f"⚙️ **Service**\nName: {svc['name']}\nPrice: {svc['price']}\nType: {svc['type']}"
    keyboard = [[InlineKeyboardButton("🗑️ Delete", callback_data=f"svc_del_{sid}")], [InlineKeyboardButton("⬅️ Back", callback_data="admin_list_svc")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_service_btn(update, context):
    sid = int(update.callback_query.data.split("_")[2])
    await db.delete_service(sid)
    await update.callback_query.answer("Deleted")
    await list_services_btn(update, context)

async def stats_btn(update, context):
    cnt = await db.get_all_users_count()
    await update.callback_query.edit_message_text(f"Users: {cnt}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_home")]]))

# --- Settings & Others ---
async def settings_menu(update, context):
    query = update.callback_query
    ref_bonus = await db.get_setting('ref_bonus')
    text = f"⚙️ **Settings**\nRef Bonus: {ref_bonus} TK"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Edit Ref Bonus", callback_data="set_ref_edit"), InlineKeyboardButton("⬅️ Back", callback_data="admin_home")]]))

async def start_edit_ref(update, context):
    await update.callback_query.message.reply_text("New Amount:")
    return SETTINGS_REF_BONUS

async def set_ref_bonus(update, context):
    try:
        await db.set_setting('ref_bonus', int(update.message.text))
        await update.message.reply_text("✅ Saved", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_home")]]))
    except: pass
    return ConversationHandler.END

async def codes_menu(update, context):
    query = update.callback_query
    text = "🎁 **Redeem Codes**"
    keyboard = [[InlineKeyboardButton("➕ Create Code", callback_data="code_add"), InlineKeyboardButton("📋 List/Del", callback_data="code_list")], [InlineKeyboardButton("⬅️ Back", callback_data="admin_home")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def start_add_code(update, context):
    await update.callback_query.message.reply_text("Amount:")
    return ADD_CODE_VAL

async def add_code_val(update, context):
    try: context.user_data['code_amount'] = int(update.message.text); await update.message.reply_text("Max Uses:"); return ADD_CODE_USES
    except: return ADD_CODE_VAL

async def add_code_uses(update, context):
    try:
        import random, string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        await db.create_redeem_code(code, context.user_data['code_amount'], int(update.message.text))
        await update.message.reply_text(f"✅ Code: `{code}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_home")]]))
    except: pass
    return ConversationHandler.END

async def list_codes(update, context):
    codes = await db.get_all_codes()
    if not codes: await update.callback_query.edit_message_text("No Codes", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_codes")]])); return
    keyboard = []
    for c in codes: keyboard.append([InlineKeyboardButton(f"{c['code']} ({c['used_count']}/{c['max_uses']})", callback_data=f"del_code_{c['code']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_codes")])
    await update.callback_query.edit_message_text("Click to Delete:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_code_btn(update, context):
    await db.delete_code(update.callback_query.data.split("_")[2])
    await list_codes(update, context)

async def start_add_stock(update, context):
    if update.callback_query: await update.callback_query.answer()
    services = await db.get_services()
    txt = "Enter Svc ID:\n" + "\n".join([f"{s['id']}:{s['name']}" for s in services])
    await update.effective_message.reply_text(txt)
    return ADD_STOCK_SVC

async def add_stock_svc(update, context):
    try: context.user_data['stock_sid'] = int(update.message.text); await update.message.reply_text("Content:"); return ADD_STOCK_CONTENT
    except: return ADD_STOCK_SVC

async def add_stock_content(update, context):
    await db.add_stock(context.user_data['stock_sid'], update.message.text)
    await update.message.reply_text("✅ Added", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_home")]]))
    return ConversationHandler.END

async def start_broadcast(update, context):
    if update.callback_query: await update.callback_query.answer()
    await update.effective_message.reply_text("Msg:")
    return BROADCAST_MSG

async def broadcast_send(update, context):
    msg = update.message.text
    ids = await db.get_all_users_ids()
    sender = Bot(USER_BOT_TOKEN)
    for i in ids: 
        try: await sender.send_message(i, msg); await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ Sent", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data="admin_home")]]))
    return ConversationHandler.END

async def start_pay(update, context):
    if update.callback_query: await update.callback_query.answer()
    await update.effective_message.reply_text("/pay [ID] [Amt]")

async def manage_balance_cmd(update, context):
    if not is_admin(update.effective_user.id): return
    try: await db.update_balance(int(context.args[0]), int(context.args[1]), True); await update.message.reply_text("Done")
    except: pass

async def cancel(update, context):
    await update.message.reply_text("Cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="admin_home")]]))
    return ConversationHandler.END

def setup_admin_bot(application):
    application.add_handler(CommandHandler("start", admin_start))
    application.add_handler(CallbackQueryHandler(admin_start, pattern="^admin_home"))
    
    # Pendings
    application.add_handler(CallbackQueryHandler(list_pending_orders, pattern="^admin_pending"))
    application.add_handler(CallbackQueryHandler(view_order, pattern="^ord_view_"))
    application.add_handler(CallbackQueryHandler(order_action, pattern="^ord_act_"))
    
    # Services
    application.add_handler(CallbackQueryHandler(list_services_btn, pattern="^admin_list_svc"))
    application.add_handler(CallbackQueryHandler(service_options, pattern="^svc_opt_"))
    application.add_handler(CallbackQueryHandler(delete_service_btn, pattern="^svc_del_"))
    
    # Settings & Codes
    application.add_handler(CallbackQueryHandler(settings_menu, pattern="^admin_settings"))
    application.add_handler(CallbackQueryHandler(codes_menu, pattern="^admin_codes"))
    application.add_handler(CallbackQueryHandler(list_codes, pattern="^code_list"))
    application.add_handler(CallbackQueryHandler(delete_code_btn, pattern="^del_code_"))

    application.add_handler(CallbackQueryHandler(stats_btn, pattern="^admin_stats"))
    application.add_handler(CallbackQueryHandler(start_pay, pattern="^admin_pay"))
    application.add_handler(CommandHandler("pay", manage_balance_cmd))
    
    cancel_handlers = [CommandHandler("cancel", cancel), CommandHandler("start", admin_start)]
    
    # Convos
    # Settings
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_ref, pattern="^set_ref_edit")],
        states={SETTINGS_REF_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ref_bonus)]},
        fallbacks=cancel_handlers
    ))
    # Codes
    application.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_code, pattern="^code_add")],
        states={
            ADD_CODE_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_code_val)],
            ADD_CODE_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_code_uses)]
        },
        fallbacks=cancel_handlers
    ))
    # Services (UPDATED)
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add_service", start_add_svc), CallbackQueryHandler(start_add_svc, pattern="^admin_add_svc")],
        states={
            ADD_SVC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_name)],
            ADD_SVC_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_price)],
            ADD_SVC_TYPE: [CallbackQueryHandler(add_service_type, pattern="^type_")],
            ADD_SVC_QUESTION: [
                CallbackQueryHandler(add_service_question, pattern="^input_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_question)
            ],
        },
        fallbacks=cancel_handlers
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add_stock", start_add_stock), CallbackQueryHandler(start_add_stock, pattern="^admin_add_stock")],
        states={
            ADD_STOCK_SVC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_svc)],
            ADD_STOCK_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_content)],
        },
        fallbacks=cancel_handlers
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("broadcast", start_broadcast), CallbackQueryHandler(start_broadcast, pattern="^admin_broadcast")],
        states={BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=cancel_handlers
    ))
