import os

# Tokens are now loaded from Environment Variables (Render/Server)
# For local run, you can set these in your system or a .env file
USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN", "YOUR_USER_BOT_TOKEN_HERE")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "YOUR_ADMIN_BOT_TOKEN_HERE")

# List of Admin User IDs
ADMIN_IDS = [
    6787688428, # Your ID
]

# Database Path
DB_PATH = "bot_database.db"
