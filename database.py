
import aiosqlite
import datetime
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Users Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    referrer_id INTEGER,
                    total_referrals INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0,
                    joined_at TIMESTAMP,
                    language TEXT DEFAULT 'bn',
                    last_daily_check TIMESTAMP
                )
            ''')

            # Migration for existing DB
            try:
                await db.execute("ALTER TABLE users ADD COLUMN last_daily_check TIMESTAMP")
                await db.commit()
            except: pass # Already exists

            # Services Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    price INTEGER,
                    type TEXT, 
                    description TEXT,
                    question TEXT
                )
            ''')
            # Stock Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id INTEGER,
                    content TEXT,
                    added_at TIMESTAMP,
                    FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
                )
            ''')
            # Orders Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service_id INTEGER,
                    content TEXT,
                    price INTEGER,
                    status TEXT,
                    user_input TEXT,
                    purchased_at TIMESTAMP
                )
            ''')
            # Settings Table (Key-Value)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Redeem Codes Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS redeem_codes (
                    code TEXT PRIMARY KEY,
                    amount INTEGER,
                    max_uses INTEGER DEFAULT 1,
                    used_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP
                )
            ''')
            # Redeem History Table (Prevent double use)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS redeem_history (
                    user_id INTEGER,
                    code TEXT,
                    used_at TIMESTAMP,
                    PRIMARY KEY (user_id, code)
                )
            ''')

            # Initialize default Refer Bonus if not exists
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '10')")

            await db.commit()

    # --- Settings Methods ---
    async def get_setting(self, key):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else None

    async def set_setting(self, key, value):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            await db.commit()

    # --- Redeem Code Methods ---
    async def create_redeem_code(self, code, amount, max_uses=1):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("INSERT INTO redeem_codes (code, amount, max_uses, created_at) VALUES (?, ?, ?, ?)", 
                                 (code, amount, max_uses, datetime.datetime.now()))
                await db.commit()
                return True
            except: return False

    async def get_redeem_code(self, code):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM redeem_codes WHERE code = ?", (code,)) as cursor:
                 row = await cursor.fetchone()
                 return dict(row) if row else None

    async def use_redeem_code(self, code, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            # Check valid
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM redeem_codes WHERE code = ?", (code,)) as cursor:
                item = await cursor.fetchone()
            
            if not item: return "invalid"
            if item['used_count'] >= item['max_uses']: return "exhausted"

            # Check history
            async with db.execute("SELECT * FROM redeem_history WHERE user_id = ? AND code = ?", (user_id, code)) as cursor:
                 if await cursor.fetchone():
                     return "already_used"

            # Execute Usage
            amount = item['amount']
            used_at = datetime.datetime.now()
            
            await db.execute("UPDATE redeem_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
            await db.execute("INSERT INTO redeem_history (user_id, code, used_at) VALUES (?, ?, ?)", (user_id, code, used_at))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return amount

    async def get_all_codes(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM redeem_codes") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def delete_code(self, code):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
            await db.commit()


    # --- User Methods ---
    async def get_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()

    async def add_user(self, user_id, first_name, username, referrer_id=None):
        async with aiosqlite.connect(self.db_path) as db:
            users_check = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if await users_check.fetchone():
                return False
            joined_at = datetime.datetime.now()
            await db.execute('''
                INSERT INTO users (user_id, first_name, username, referrer_id, joined_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, first_name, username, referrer_id, joined_at))
            
            await db.commit()
            return True

    async def update_balance(self, user_id, amount, add=True):
        async with aiosqlite.connect(self.db_path) as db:
            if add:
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            else:
                await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
    
    async def set_language(self, user_id, lang):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
            await db.commit()

    async def update_daily_check(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.now()
            await db.execute("UPDATE users SET last_daily_check = ? WHERE user_id = ?", (now, user_id))
            await db.commit()

    # --- Referral Methods ---
    async def add_referral_reward(self, referrer_id, amount):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users 
                SET balance = balance + ?, 
                    total_referrals = total_referrals + 1, 
                    total_earned = total_earned + ? 
                WHERE user_id = ?
            ''', (amount, amount, referrer_id))
            await db.commit()
            
    async def get_top_users(self, limit=10):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, first_name, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)) as cursor:
                return await cursor.fetchall()
                
    async def get_all_users_count(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    # --- Service Methods ---
    async def add_service(self, name, price, type, description="", question=None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO services (name, price, type, description, question) VALUES (?, ?, ?, ?, ?)", 
                             (name, price, type, description, question))
            await db.commit()

    async def get_services(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM services") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
    async def get_service(self, service_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM services WHERE id = ?", (service_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def delete_service(self, service_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
            await db.commit()

    async def update_service_price(self, service_id, new_price):
        async with aiosqlite.connect(self.db_path) as db:
             await db.execute("UPDATE services SET price = ? WHERE id = ?", (new_price, service_id))
             await db.commit()

    # --- Stock Methods ---
    async def add_stock(self, service_id, content):
        async with aiosqlite.connect(self.db_path) as db:
            added_at = datetime.datetime.now()
            await db.execute("INSERT INTO stock (service_id, content, added_at) VALUES (?, ?, ?)", 
                             (service_id, content, added_at))
            await db.commit()

    async def get_stock_count(self, service_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM stock WHERE service_id = ?", (service_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0]

    async def fetch_stock_item(self, service_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get the oldest item
            async with db.execute("SELECT * FROM stock WHERE service_id = ? ORDER BY id ASC LIMIT 1", (service_id,)) as cursor:
                item = await cursor.fetchone()
            
            if item:
                # Delete it
                await db.execute("DELETE FROM stock WHERE id = ?", (item['id'],))
                await db.commit()
                return item['content']
            return None

    # --- Order Methods ---
    async def log_order(self, user_id, service_id, content, price, status='completed', user_input=None):
        async with aiosqlite.connect(self.db_path) as db:
            purchased_at = datetime.datetime.now()
            await db.execute('''
                INSERT INTO orders (user_id, service_id, content, price, status, user_input, purchased_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, service_id, content, price, status, user_input, purchased_at))
            await db.commit()
            
    async def get_all_users_ids(self):
         async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def get_pending_orders(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Join with Services to get Name
            query = '''
                SELECT o.*, s.name as service_name 
                FROM orders o 
                LEFT JOIN services s ON o.service_id = s.id
                WHERE o.status = 'pending'
            '''
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_order(self, order_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Join to get service name
            query = '''
                SELECT o.*, s.name as service_name 
                FROM orders o 
                LEFT JOIN services s ON o.service_id = s.id
                WHERE o.id = ?
            '''
            async with db.execute(query, (order_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_order_status(self, order_id, status):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            await db.commit()
