
import asyncio
from telegram import Bot
from config import USER_BOT_TOKEN, ADMIN_BOT_TOKEN

async def get_info():
    user_bot = Bot(USER_BOT_TOKEN)
    admin_bot = Bot(ADMIN_BOT_TOKEN)
    
    u_info = await user_bot.get_me()
    a_info = await admin_bot.get_me()
    
    print(f"User Bot Link: https://t.me/{u_info.username}")
    print(f"Admin Bot Link: https://t.me/{a_info.username}")

if __name__ == "__main__":
    asyncio.run(get_info())
