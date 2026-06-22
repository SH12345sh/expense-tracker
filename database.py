import sqlite3

conn = sqlite3.connect("expenses.db")
cursor = conn.cursor()

# 1. NEW: Create the users credential storage table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

# 2. UPDATED: Added user_id column to associate expenses with a specific account
cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount TEXT,
    category TEXT,
    date TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

# 3. UPDATED: Added user_id column to associate income with a specific account
cursor.execute("""
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount TEXT,
    source TEXT,
    date TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

conn.commit()

# NOTE: For your metric checks (like highest expense), you will filter by the 
# logged-in user in your server routes like this:
# "SELECT MAX(CAST(amount AS INTEGER)) FROM expenses WHERE user_id = ?"
cursor.execute(
    "SELECT MAX(CAST(amount AS INTEGER)) FROM expenses"
)

highest_expense = cursor.fetchone()[0]

if highest_expense is None:
    highest_expense = 0
    
conn.close()

print("Database and User Authentication Schema initialized successfully!")