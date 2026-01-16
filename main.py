
import asyncio
import nest_asyncio
import os
from aiohttp import web
from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest
from config import USER_BOT_TOKEN, ADMIN_BOT_TOKEN
from database import Database
from user_bot import setup_user_bot
from admin_bot import setup_admin_bot

nest_asyncio.apply()

async def main():
    # 1. Initialize Database
    db = Database()
    await db.init_db()
    print("✅ Database Initialized.")

    # 2. Build Apps with custom request timeouts
    # Increasing timeout to avoid "TimedOut" errors on slow connections
    trequest = HTTPXRequest(connection_pool_size=8, connect_timeout=60, read_timeout=60, write_timeout=60)
    
    print("🤖 Building Bots... (Version 2.1 - Notification Fix Verified)")
    user_app = ApplicationBuilder().token(USER_BOT_TOKEN).request(trequest).build()
    setup_user_bot(user_app)

    admin_app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).request(trequest).build()
    setup_admin_bot(admin_app)

    # 3. Initialize & Start User Bot
    print("🚀 Starting User Bot...")
    await user_app.initialize()
    await user_app.start()
    await user_app.updater.start_polling(allowed_updates=True)

    # 4. Initialize & Start Admin Bot
    print("🚀 Starting Admin Bot...")
    await admin_app.initialize()
    await admin_app.start()
    await admin_app.updater.start_polling(allowed_updates=True)

    # 5. Start Keep-Alive Web Server
    async def health_check(request):
        return web.Response(text="Bot is alive!")

    app = web.Application()
    app.add_routes([web.get('/', health_check)])
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()
    print(f"🌍 Web Server started on port {os.environ.get('PORT', 8080)}")

    print("✅ Both Bots are Running! (Press Ctrl+C to stop)")
    
    # 5. Keep alive
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("🛑 Stopping Bots...")
        if user_app.updater.running:
             await user_app.updater.stop()
        if user_app.running:
             await user_app.stop()
             await user_app.shutdown()
        
        if admin_app.updater.running:
             await admin_app.updater.stop()
        if admin_app.running:
             await admin_app.stop()
             await admin_app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exited by User.")
