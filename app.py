from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, 'expenses.db')
app.secret_key = 'your_super_secret_session_passcode_here' # <-- ADD THIS LINE

# --- 1. HOME / LANDING PAGE ---
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard')) # Redirect straight to app if already logged in
    return render_template('home.html')

# --- 2. SIGN UP ROUTE ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            return "Username and Password cannot be empty!", 400
            
        hashed_password = generate_password_hash(password)
        
        # 1. Open the connection BEFORE the try block so it's accessible everywhere
        conn = sqlite3.connect(DB_PATH, timeout=10) # Added timeout safety helper
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            # Redirect immediately if successful
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError:
            return "Username already exists! Try another one.", 400
            
        finally:
            # 2. This code ALWAYS runs, even if an IntegrityError happens!
            conn.close()
            
    return render_template('signup.html')

# --- 3. SIGN IN / LOGIN ROUTE ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return "Invalid Username or Password!", 401
            
    return render_template('login.html')

# --- 4. LOGOUT ROUTE ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    # 1. GATEKEEPER: If user is not logged in, boot them to the login screen
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    # Get the current logged-in user's ID from the active session
    current_user_id = session['user_id']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Filter expenses count for just THIS user
    cursor.execute("SELECT * FROM expenses WHERE user_id = ?", (current_user_id,))
    expenses = cursor.fetchall()
    transaction_count = len(expenses)

    # 3. Filter total expense sum for just THIS user
    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM expenses WHERE user_id = ?", (current_user_id,))
    total = cursor.fetchone()[0]
    if total is None:
        total = 0

    # 4. Filter total income sum for just THIS user
    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM income WHERE user_id = ?", (current_user_id,))
    total_income = cursor.fetchone()[0]
    if total_income is None:
        total_income = 0

    balance = total_income - total

    # 5. Filter the 5 most recent expenses for just THIS user
    cursor.execute("""
        SELECT amount, category, date
        FROM expenses
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (current_user_id,))
    recent_expenses = cursor.fetchall()

    # 6. Filter highest expense logic for just THIS user
    cursor.execute(
        "SELECT MAX(CAST(amount AS INTEGER)) FROM expenses WHERE user_id = ?", 
        (current_user_id,)
    )
    highest_expense = cursor.fetchone()[0]
    if highest_expense is None:
        highest_expense = 0

    conn.close()

    return render_template(
        'index.html',
        total=total,
        total_income=total_income,
        balance=balance,
        transaction_count=transaction_count,
        recent_expenses=recent_expenses,
        highest_expense=highest_expense
    )

# --- 2. ADD EXPENSE ROUTE ---
@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    # SECURITY GATE: Boot out unauthenticated users
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']
        user_id = session['user_id'] # <-- Pull the active user identification token

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # UPDATED: Insert the user_id alongside your metric entries
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, category, date)
        )

        conn.commit()
        conn.close()

        # FIX: Send users straight back to the working application view dashboard
        return redirect(url_for('dashboard'))

    return render_template('add_expense.html')

# --- 3. INCOME ENTRY ROUTE ---
@app.route('/income', methods=['GET', 'POST'])
def income():
    # SECURITY GATE: Boot out unauthenticated users
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = request.form['amount']
        source = request.form['source']
        date = request.form['date']
        user_id = session['user_id'] # <-- Pull the active user identification token

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # UPDATED: Insert the user_id alongside your metric entries
        cursor.execute(
            "INSERT INTO income (user_id, amount, source, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, source, date)
        )

        conn.commit()
        conn.close()

        # FIX: Send users straight back to the working application view dashboard
        return redirect(url_for('dashboard'))

    return render_template('income.html')

@app.route("/history")
def history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    search_inc = request.args.get("search_income", "")
    search_exp = request.args.get("search_expense", "")

    # 1. Handle Income Queries
    if search_inc:
        cursor.execute(
            "SELECT * FROM income WHERE source LIKE ?",
            ("%" + search_inc + "%",),
        )
    else:
        cursor.execute("SELECT * FROM income")
    incomes = cursor.fetchall()

    # 2. Handle Expense Queries
    if search_exp:
        cursor.execute(
            "SELECT * FROM expenses WHERE category LIKE ?",
            ("%" + search_exp + "%",),
        )
    else:
        cursor.execute("SELECT * FROM expenses")
    expenses = cursor.fetchall()

    conn.close()

    # CRUCIAL CHANGE: If the request comes from JavaScript, return raw JSON data
    if (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):  # Checks if it's an AJAX call
        return jsonify({"incomes": incomes, "expenses": expenses})

    # Otherwise, load the page normally on initial visit
    return render_template("history.html", incomes=incomes, expenses=expenses)
    
@app.route('/delete/<int:id>')
def delete(id):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expenses WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/')

@app.route('/reports')
def reports():

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM income")
    total_income = cursor.fetchone()[0]

    if total_income is None:
        total_income = 0

    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM expenses")
    total_expense = cursor.fetchone()[0]

    if total_expense is None:
        total_expense = 0

    balance = total_income - total_expense

    if total_income > 0:
        savings_percentage = round((balance / total_income) * 100, 2)
        # Added the missing calculation for your new analytical report metrics
        expense_ratio = round((total_expense / total_income) * 100, 2)
    else:
        savings_percentage = 0
        expense_ratio = 0

    conn.close()

    # Passing all variables to your updated analytics page layout perfectly
    return render_template(
        'reports.html',
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        savings_percentage=savings_percentage,
        expense_ratio=expense_ratio
    )

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    # Security Gate: If not logged in, redirect to login screen
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        # Secure Update: Only allow update if this transaction belongs to the logged-in user
        cursor.execute(
            """
            UPDATE expenses
            SET amount=?,
                category=?,
                date=?
            WHERE id=? AND user_id=?
            """,
            (amount, category, date, id, current_user_id)
        )

        conn.commit()
        conn.close()
        return redirect('/history')

    # Secure Select: Fetch data only if it belongs to this logged-in user
    cursor.execute(
        "SELECT * FROM expenses WHERE id=? AND user_id=?",
        (id, current_user_id)
    )
    expense = cursor.fetchone()
    conn.close()

    # Fallback if someone manually guesses an unauthorized ID in the URL
    if expense is None:
        return "Record not found or unauthorized!", 404

    return render_template(
        'edit_expense.html',
        expense=expense
    )

@app.route('/delete_income/<int:id>')
def delete_income(id):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM income WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/history')

@app.route('/edit_income/<int:id>', methods=['GET', 'POST'])
def edit_income(id):
    # Security Gate: If not logged in, redirect to login screen
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    conn = sqlite3.connect("DB_PATH")
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = request.form['amount']
        source = request.form['source']
        date = request.form['date']

        # Secure Update: Only allow update if this income record belongs to the logged-in user
        cursor.execute(
            """
            UPDATE income
            SET amount=?,
                source=?,
                date=?
            WHERE id=? AND user_id=?
            """,
            (amount, source, date, id, current_user_id)
        )

        conn.commit()
        conn.close()
        return redirect('/history')

    # Secure Select: Fetch data only if it belongs to this logged-in user
    cursor.execute(
        "SELECT * FROM income WHERE id=? AND user_id=?",
        (id, current_user_id)
    )
    income = cursor.fetchone()
    conn.close()

    # Fallback if someone manually guesses an unauthorized ID in the URL
    if income is None:
        return "Record not found or unauthorized!", 404

    return render_template(
        'edit_income.html',
        income=income
    )

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect('/login')
        
    user_id = session['user_id']
    db_path = os.path.join('/data', 'expenses.db') if os.path.isdir('/data') else 'expenses.db'
    
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    
    # Safely verify that our columns exist in the database (migration check)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN budget_threshold INTEGER DEFAULT 80")
        cursor.execute("ALTER TABLE users ADD COLUMN currency TEXT DEFAULT '₹'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Columns already exist

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Action 1: Update financial constraints
        if action == 'update_finance':
            monthly_budget = request.form.get('monthly_budget', 0.0)
            threshold = request.form.get('budget_threshold', 80)
            currency = request.form.get('currency', '₹')
            
            cursor.execute("""
                UPDATE users 
                SET monthly_budget = ?, budget_threshold = ?, currency = ? 
                WHERE id = ?
            """, (monthly_budget, threshold, currency, user_id))
            conn.commit()
            
            # Save currency choice into session so other pages can use it instantly
            session['currency'] = currency
            flash("Financial rules and configurations updated successfully!", "success")
            
        # Action 2: Reset transaction ledger data only
        elif action == 'clear_history':
            cursor.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
            conn.commit()
            flash("All expense and income records have been completely cleared!", "success")
            
        conn.close()
        return redirect('/settings')
        
    # GET Request: Fetch live user profile configurations
    cursor.execute("SELECT username, monthly_budget, budget_threshold, currency FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    return render_template('settings.html', user_data=user_data)


# Supplementary Log tracking layout route matching action option item 3
@app.route('/settings/activity')
def security_activity():
    if 'user_id' not in session:
        return redirect('/login')
    # Simple mockup routing page displaying isolated active instance access points
    return "<body style='font-family:sans-serif; padding:40px; background:#f1f5f9;'><div style='background:white; padding:30px; border-radius:8px; max-width:500px; margin:auto;'><h2>Login Activity Logs</h2><hr><p>🟢 Session Active now - Current Web Browser Instance Node</p><p style='color:#64748b;'>Last login authentication checklist verified successfully today.</p><br><a href='/settings' style='color:#3b82f6;'>&larr; Back to Settings</a></div></body>"

# This forces Render/Gunicorn to only use 1 worker process automatically
os.environ['WEB_CONCURRENCY'] = '1'

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # 2. Expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # 🌟 FIX: Add the missing Income table!
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Run the database creator first!
    init_db() 
    # Then start your app
    app.run(debug=True)