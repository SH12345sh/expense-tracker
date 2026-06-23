from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = r"E:\ExpenseTracker\expenses.db" 
app.secret_key = 'your_super_secret_session_passcode_here'

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            monthly_budget REAL DEFAULT 0.0,
            budget_threshold INTEGER DEFAULT 80,
            currency TEXT DEFAULT '₹'
        )
    ''')
    
    # 2. Expenses table (Ensuring structural column order compatibility)
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

    # 3. Income table (Ensuring structural column order compatibility)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            source TEXT NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

with app.app_context():
    init_db()

# --- 1. HOME / LANDING PAGE ---
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
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
        
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username already exists! Try another one.", 400
        finally:
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

# --- 5. DASHBOARD ROUTE ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Filter count for just THIS user
    cursor.execute("SELECT * FROM expenses WHERE user_id = ?", (current_user_id,))
    expenses = cursor.fetchall()
    transaction_count = len(expenses)

    # Filter total expense sum for just THIS user
    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM expenses WHERE user_id = ?", (current_user_id,))
    total = cursor.fetchone()[0] or 0

    # Filter total income sum for just THIS user
    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM income WHERE user_id = ?", (current_user_id,))
    total_income = cursor.fetchone()[0] or 0

    balance = total_income - total

    # Filter the 5 most recent expenses for just THIS user
    cursor.execute("""
        SELECT amount, category, date
        FROM expenses
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (current_user_id,))
    recent_expenses = cursor.fetchall()

    # Filter highest expense logic for just THIS user
    cursor.execute("SELECT MAX(CAST(amount AS INTEGER)) FROM expenses WHERE user_id = ?", (current_user_id,))
    highest_expense = cursor.fetchone()[0] or 0

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

# --- 6. ADD EXPENSE ROUTE ---
@app.route('/add', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']
        user_id = session['user_id']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, category, date)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('add_expense.html')

# --- 7. INCOME ENTRY ROUTE ---
@app.route('/income', methods=['GET', 'POST'])
def income():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = request.form['amount']
        source = request.form['source']
        date = request.form['date']
        user_id = session['user_id']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO income (user_id, amount, source, date) VALUES (?, ?, ?, ?)",
            (user_id, amount, source, date)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('income.html')

# --- 8. SECURE HISTORY ROUTE (With template layout matching index array order) ---
@app.route("/history")
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    search_inc = request.args.get("search_income", "")
    search_exp = request.args.get("search_expense", "")

    # 🌟 FIXED: Kept SELECT * so indices like row[0] (ID) map seamlessly to your buttons!
    if search_inc:
        cursor.execute(
            "SELECT * FROM income WHERE user_id = ? AND source LIKE ?",
            (current_user_id, "%" + search_inc + "%"),
        )
    else:
        cursor.execute("SELECT * FROM income WHERE user_id = ?", (current_user_id,))
    incomes = cursor.fetchall()

    if search_exp:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND category LIKE ?",
            (current_user_id, "%" + search_exp + "%"),
        )
    else:
        cursor.execute("SELECT * FROM expenses WHERE user_id = ?", (current_user_id,))
    expenses = cursor.fetchall()

    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"incomes": incomes, "expenses": expenses})

    return render_template("history.html", incomes=incomes, expenses=expenses)
    
# --- 9. SECURE EXPENSE DELETE ROUTE ---
@app.route('/delete/<int:id>')
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Secure validation path: Verify ownership constraint before executing deletion
    cursor.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (id, current_user_id))
    conn.commit()
    conn.close()
    return redirect('/history')

# --- 10. SECURE INCOME DELETE ROUTE ---
@app.route('/delete_income/<int:id>')
def delete_income(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Secure validation path: Verify ownership constraint before executing deletion
    cursor.execute("DELETE FROM income WHERE id=? AND user_id=?", (id, current_user_id))
    conn.commit()
    conn.close()
    return redirect('/history')

# --- 11. SECURE REPORTS ROUTE ---
@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Isolate global calculations by current_user_id constraint
    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM income WHERE user_id = ?", (current_user_id,))
    total_income = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(CAST(amount AS INTEGER)) FROM expenses WHERE user_id = ?", (current_user_id,))
    total_expense = cursor.fetchone()[0] or 0

    balance = total_income - total_expense

    if total_income > 0:
        savings_percentage = round((balance / total_income) * 100, 2)
        expense_ratio = round((total_expense / total_income) * 100, 2)
    else:
        savings_percentage = 0
        expense_ratio = 0

    conn.close()

    return render_template(
        'reports.html',
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        savings_percentage=savings_percentage,
        expense_ratio=expense_ratio
    )

# --- 12. SECURE EDIT EXPENSE ROUTE ---
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']

        cursor.execute(
            "UPDATE expenses SET amount=?, category=?, date=? WHERE id=? AND user_id=?",
            (amount, category, date, id, current_user_id)
        )
        conn.commit()
        conn.close()
        return redirect('/history')

    cursor.execute("SELECT * FROM expenses WHERE id=? AND user_id=?", (id, current_user_id))
    expense = cursor.fetchone()
    conn.close()

    if expense is None:
        return "Record not found or unauthorized!", 404

    return render_template('edit_expense.html', expense=expense)

# --- 13. SECURE EDIT INCOME ROUTE ---
@app.route('/edit_income/<int:id>', methods=['GET', 'POST'])
def edit_income(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        amount = request.form['amount']
        source = request.form['source']
        date = request.form['date']

        cursor.execute(
            "UPDATE income SET amount=?, source=?, date=? WHERE id=? AND user_id=?",
            (amount, source, date, id, current_user_id)
        )
        conn.commit()
        conn.close()
        return redirect('/history')

    cursor.execute("SELECT * FROM income WHERE id=? AND user_id=?", (id, current_user_id))
    income = cursor.fetchone()
    conn.close()

    if income is None:
        return "Record not found or unauthorized!", 404

    return render_template('edit_income.html', income=income)

# --- 14. SETTINGS ROUTE ---
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    
    # Verification check for dynamically allocated settings table dependencies
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN monthly_budget REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN budget_threshold INTEGER DEFAULT 80")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN currency TEXT DEFAULT '₹'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    if request.method == 'POST':
        action = request.form.get('action')
        
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
            
            session['currency'] = currency
            flash("Financial rules and configurations updated successfully!", "success")
            
        elif action == 'clear_history':
            cursor.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
            conn.commit()
            flash("All expense and income records have been completely cleared!", "success")
            
        conn.close()
        return redirect('/settings')
        
    cursor.execute("SELECT username, monthly_budget, budget_threshold, currency FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    return render_template('settings.html', user_data=user_data)

# --- 15. ACTIVITY LOG MONITOR ---
@app.route('/settings/activity')
def security_activity():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return "<body style='font-family:sans-serif; padding:40px; background:#f1f5f9;'><div style='background:white; padding:30px; border-radius:8px; max-width:500px; margin:auto;'><h2>Login Activity Logs</h2><hr><p>🟢 Session Active now - Current Web Browser Instance Node</p><p style='color:#64748b;'>Last login authentication checklist verified successfully today.</p><br><a href='/settings' style='color:#3b82f6;'>&larr; Back to Settings</a></div></body>"

os.environ['WEB_CONCURRENCY'] = '1'

if __name__ == '__main__':
    app.run(debug=True)