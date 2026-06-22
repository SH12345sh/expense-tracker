import sqlite3

# Open your exact database file
conn = sqlite3.connect("expenses.db")
cursor = conn.cursor()

try:
    # Add the new budget column safely
    cursor.execute("ALTER TABLE users ADD COLUMN monthly_budget REAL DEFAULT 0.0")
    conn.commit()
    print("Database updated successfully!")
except sqlite3.OperationalError:
    print("Database was already updated before.")

conn.close()