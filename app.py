from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import hashlib
import pandas as pd
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import base64
import numpy as np
import json
import os
import shutil
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

# Create the Flask application
app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-it-later'

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# User Model (this creates a table in database)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Transaction Model (for income and expenses)
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to User
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

# Create database tables (run this once)
with app.app_context():
    db.create_all()
    print("Database created successfully!")

# ==================== HOME & AUTHENTICATION ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email', '')
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!', 'error')
            return redirect(url_for('register'))
        
        # Hash password (simple encryption)
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Create new user
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Hash the entered password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Find user in database
        user = User.query.filter_by(username=username, password=hashed_password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# ==================== DASHBOARD ROUTE (UPDATED WITH PREDICTION) ====================

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get all transactions for this user
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
    expense_transactions = [t for t in transactions if t.type == 'expense']
    
    # Calculate totals
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    balance = total_income - total_expense
    
    # Get recent 5 transactions
    recent_transactions = transactions[:5]
    
    # Prediction for dashboard (if enough data)
    prediction_data = None
    if len(expense_transactions) >= 3:
        sorted_expenses = sorted(expense_transactions, key=lambda x: x.date)
        pred = predict_future_expenses(sorted_expenses)
        prediction_data = {
            'next_month': pred['next_month_total'],
            'trend': pred['trend']
        }
    
    return render_template('dashboard.html', 
                         total_income=total_income, 
                         total_expense=total_expense,
                         balance=balance,
                         recent_transactions=recent_transactions,
                         username=session['username'],
                         prediction_data=prediction_data)

# ==================== TRANSACTION MANAGEMENT ====================

@app.route('/add_transaction', methods=['GET', 'POST'])
def add_transaction():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        trans_type = request.form['type']
        amount = float(request.form['amount'])
        category = request.form['category']
        description = request.form.get('description', '')
        date_str = request.form.get('date')
        
        # Parse date
        if date_str:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            date = datetime.utcnow()
        
        # Create new transaction
        new_transaction = Transaction(
            user_id=user_id,
            type=trans_type,
            amount=amount,
            category=category,
            description=description,
            date=date
        )
        
        db.session.add(new_transaction)
        db.session.commit()
        
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('add_transaction.html', today=today)

@app.route('/view_transactions', methods=['GET'])
def view_transactions():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Base query
    query = Transaction.query.filter_by(user_id=user_id)
    
    # Get filter parameters
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    min_amount = request.args.get('min_amount')
    max_amount = request.args.get('max_amount')
    
    # Apply filters
    if category and category != '':
        query = query.filter_by(category=category)
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Transaction.date >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)
        query = query.filter(Transaction.date <= end)
    
    if min_amount:
        query = query.filter(Transaction.amount >= float(min_amount))
    
    if max_amount:
        query = query.filter(Transaction.amount <= float(max_amount))
    
    # Order by date descending
    transactions = query.order_by(Transaction.date.desc()).all()
    
    return render_template('view_transactions.html', 
                         transactions=transactions,
                         filter_category=category,
                         start_date=start_date,
                         end_date=end_date,
                         min_amount=min_amount,
                         max_amount=max_amount)

@app.route('/edit_transaction/<int:id>', methods=['POST'])
def edit_transaction(id):
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    transaction = Transaction.query.get_or_404(id)
    
    # Check if transaction belongs to current user
    if transaction.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('view_transactions'))
    
    # Update fields
    transaction.type = request.form['type']
    transaction.amount = float(request.form['amount'])
    transaction.category = request.form['category']
    transaction.description = request.form.get('description', '')
    
    date_str = request.form.get('date')
    if date_str:
        transaction.date = datetime.strptime(date_str, '%Y-%m-%d')
    
    db.session.commit()
    flash('Transaction updated successfully!', 'success')
    return redirect(url_for('view_transactions'))

@app.route('/delete_transaction/<int:id>')
def delete_transaction(id):
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    transaction = Transaction.query.get_or_404(id)
    
    # Check if transaction belongs to current user
    if transaction.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('view_transactions'))
    
    db.session.delete(transaction)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('view_transactions'))

# ==================== REPORTS ROUTE ====================

@app.route('/reports')
def reports():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    transactions = Transaction.query.filter_by(user_id=user_id).all()
    
    # Calculate totals
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    
    # Category spending (only expenses)
    category_spending = {}
    for t in transactions:
        if t.type == 'expense':
            if t.category in category_spending:
                category_spending[t.category] += t.amount
            else:
                category_spending[t.category] = t.amount
    
    # Sort by amount descending
    category_spending = dict(sorted(category_spending.items(), key=lambda x: x[1], reverse=True))
    
    return render_template('reports.html',
                         transactions=transactions,
                         total_income=total_income,
                         total_expense=total_expense,
                         category_spending=category_spending)

# ==================== VISUALIZATION ROUTES ====================

@app.route('/visualization')
def visualization():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    transactions = Transaction.query.filter_by(user_id=user_id).all()
    
    # Generate charts
    monthly_chart = generate_monthly_chart(transactions)
    category_chart = generate_category_chart(transactions)
    trend_chart = generate_trend_chart(transactions)
    
    # Get monthly summary
    monthly_data = get_monthly_summary(transactions)
    yearly_data = get_yearly_summary(transactions)
    
    return render_template('visualization.html',
                         monthly_chart=monthly_chart,
                         category_chart=category_chart,
                         trend_chart=trend_chart,
                         monthly_data=monthly_data,
                         yearly_data=yearly_data)

def generate_monthly_chart(transactions):
    """Generate monthly income vs expenses bar chart"""
    monthly_summary = {}
    
    for t in transactions:
        month_key = t.date.strftime('%Y-%m')
        if month_key not in monthly_summary:
            monthly_summary[month_key] = {'income': 0, 'expense': 0}
        
        if t.type == 'income':
            monthly_summary[month_key]['income'] += t.amount
        else:
            monthly_summary[month_key]['expense'] += t.amount
    
    if not monthly_summary:
        return None
    
    # Sort by date
    months = sorted(monthly_summary.keys())
    incomes = [monthly_summary[m]['income'] for m in months]
    expenses = [monthly_summary[m]['expense'] for m in months]
    
    # Create chart
    plt.figure(figsize=(12, 6))
    x = range(len(months))
    width = 0.35
    
    plt.bar([i - width/2 for i in x], incomes, width, label='Income', color='#27ae60', alpha=0.8)
    plt.bar([i + width/2 for i in x], expenses, width, label='Expenses', color='#e74c3c', alpha=0.8)
    
    plt.xlabel('Month', fontsize=12)
    plt.ylabel('Amount (PKR)', fontsize=12)
    plt.title('Monthly Income vs Expenses', fontsize=14, fontweight='bold')
    plt.xticks(x, months, rotation=45)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64

def generate_category_chart(transactions):
    """Generate expense by category pie chart"""
    category_expenses = {}
    
    for t in transactions:
        if t.type == 'expense':
            if t.category in category_expenses:
                category_expenses[t.category] += t.amount
            else:
                category_expenses[t.category] = t.amount
    
    if not category_expenses:
        return None
    
    # Create pie chart
    plt.figure(figsize=(10, 8))
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7B731']
    
    categories = list(category_expenses.keys())
    amounts = list(category_expenses.values())
    
    # Capitalize category names for display
    category_labels = [cat.capitalize() for cat in categories]
    
    plt.pie(amounts, labels=category_labels, autopct='%1.1f%%', colors=colors[:len(categories)], startangle=90)
    plt.title('Expense Distribution by Category', fontsize=14, fontweight='bold')
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64

def generate_trend_chart(transactions):
    """Generate spending trend line chart"""
    daily_expenses = {}
    
    for t in transactions:
        if t.type == 'expense':
            date_key = t.date.strftime('%Y-%m-%d')
            if date_key in daily_expenses:
                daily_expenses[date_key] += t.amount
            else:
                daily_expenses[date_key] = t.amount
    
    if not daily_expenses:
        return None
    
    # Sort by date
    dates = sorted(daily_expenses.keys())
    expenses = [daily_expenses[d] for d in dates]
    
    # Create line chart
    plt.figure(figsize=(12, 5))
    plt.plot(dates, expenses, marker='o', linewidth=2, markersize=4, color='#e74c3c')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Expenses (PKR)', fontsize=12)
    plt.title('Daily Spending Trend', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    plt.close()
    
    return image_base64

def get_monthly_summary(transactions):
    """Get monthly summary data"""
    monthly_data = {}
    
    for t in transactions:
        month_key = t.date.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'income': 0, 'expense': 0, 'month_name': t.date.strftime('%B %Y')}
        
        if t.type == 'income':
            monthly_data[month_key]['income'] += t.amount
        else:
            monthly_data[month_key]['expense'] += t.amount
    
    # Add balance and savings rate
    for month in monthly_data:
        monthly_data[month]['balance'] = monthly_data[month]['income'] - monthly_data[month]['expense']
        if monthly_data[month]['income'] > 0:
            monthly_data[month]['savings_rate'] = (monthly_data[month]['balance'] / monthly_data[month]['income']) * 100
        else:
            monthly_data[month]['savings_rate'] = 0
    
    # Sort by month
    return dict(sorted(monthly_data.items(), reverse=True))

def get_yearly_summary(transactions):
    """Get yearly summary data"""
    yearly_data = {}
    
    for t in transactions:
        year_key = t.date.strftime('%Y')
        if year_key not in yearly_data:
            yearly_data[year_key] = {'income': 0, 'expense': 0, 'year': year_key}
        
        if t.type == 'income':
            yearly_data[year_key]['income'] += t.amount
        else:
            yearly_data[year_key]['expense'] += t.amount
    
    # Add balance
    for year in yearly_data:
        yearly_data[year]['balance'] = yearly_data[year]['income'] - yearly_data[year]['expense']
    
    return dict(sorted(yearly_data.items(), reverse=True))

# ==================== PREDICTION MODULE ====================

@app.route('/prediction')
def prediction():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    transactions = Transaction.query.filter_by(user_id=user_id, type='expense').order_by(Transaction.date).all()
    
    if len(transactions) < 3:
        flash('Need at least 3 expense records to make predictions!', 'error')
        return redirect(url_for('dashboard'))
    
    # Prepare data for prediction
    predictions = predict_future_expenses(transactions)
    
    return render_template('prediction.html', predictions=predictions)

def predict_future_expenses(transactions):
    """Predict future expenses using machine learning"""
    
    # Prepare features
    data = []
    for t in transactions:
        data.append({
            'day_of_month': t.date.day,
            'month': t.date.month,
            'day_of_week': t.date.weekday(),
            'amount': t.amount
        })
    
    df = pd.DataFrame(data)
    
    # Use last 3 months for training
    df['days_since_start'] = range(len(df))
    
    # Linear Regression
    X = df[['days_since_start']].values
    y = df['amount'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Predict next 30 days
    last_day = len(df)
    future_days = np.array(range(last_day, last_day + 30)).reshape(-1, 1)
    future_predictions = model.predict(future_days)
    
    # Calculate statistics
    avg_expense = df['amount'].mean()
    max_expense = df['amount'].max()
    min_expense = df['amount'].min()
    
    # Predict next month total
    next_month_total = future_predictions.sum()
    
    # Get trend
    if len(df) > 1:
        last_avg = df['amount'].tail(7).mean()
        prev_avg = df['amount'].tail(14).head(7).mean()
        trend = "increasing" if last_avg > prev_avg else "decreasing"
    else:
        trend = "stable"
    
    # Identify overspending days
    threshold = avg_expense * 1.2
    overspending_days = df[df['amount'] > threshold].shape[0]
    
    # Calculate predicted savings
    total_income = sum(t.amount for t in Transaction.query.filter_by(user_id=transactions[0].user_id, type='income').all())
    months_with_data = len(set([t.date.strftime('%Y-%m') for t in Transaction.query.filter_by(user_id=transactions[0].user_id).all()]))
    avg_monthly_income = total_income / max(1, months_with_data)
    predicted_savings = avg_monthly_income - next_month_total
    
    return {
        'next_month_total': next_month_total,
        'avg_daily_expense': avg_expense,
        'max_daily_expense': max_expense,
        'min_daily_expense': min_expense,
        'trend': trend,
        'overspending_days': overspending_days,
        'total_records': len(transactions),
        'predicted_savings': predicted_savings,
        'avg_monthly_income': avg_monthly_income
    }

# ==================== BACKUP & RESTORE ====================

@app.route('/backup')
def backup():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    username = session['username']
    
    # Create backup directory if not exists
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Export user data to JSON
    transactions = Transaction.query.filter_by(user_id=user_id).all()
    user = User.query.get(user_id)
    
    backup_data = {
        'user_info': {
            'username': user.username,
            'email': user.email,
            'backup_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'transactions': []
    }
    
    for t in transactions:
        backup_data['transactions'].append({
            'type': t.type,
            'amount': t.amount,
            'category': t.category,
            'description': t.description,
            'date': t.date.strftime('%Y-%m-%d')
        })
    
    # Save backup file
    backup_filename = f"backup_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    with open(backup_path, 'w') as f:
        json.dump(backup_data, f, indent=2)
    
    # Also export to Excel
    excel_data = []
    for t in transactions:
        excel_data.append({
            'Date': t.date.strftime('%Y-%m-%d'),
            'Type': t.type.upper(),
            'Category': t.category,
            'Description': t.description or '',
            'Amount (PKR)': t.amount
        })
    
    df = pd.DataFrame(excel_data)
    excel_filename = f"export_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    excel_path = os.path.join(backup_dir, excel_filename)
    df.to_excel(excel_path, index=False)
    
    flash(f'Backup created successfully! Files: {backup_filename} and {excel_filename}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/restore', methods=['GET', 'POST'])
def restore():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    if request.method == 'POST':
        backup_file = request.files['backup_file']
        if backup_file and backup_file.filename.endswith('.json'):
            # Save uploaded file
            upload_path = os.path.join(backup_dir, backup_file.filename)
            backup_file.save(upload_path)
            
            # Restore data
            with open(upload_path, 'r') as f:
                backup_data = json.load(f)
            
            user_id = session['user_id']
            
            # Delete existing transactions
            Transaction.query.filter_by(user_id=user_id).delete()
            
            # Restore transactions
            for t_data in backup_data['transactions']:
                new_transaction = Transaction(
                    user_id=user_id,
                    type=t_data['type'],
                    amount=t_data['amount'],
                    category=t_data['category'],
                    description=t_data['description'],
                    date=datetime.strptime(t_data['date'], '%Y-%m-%d')
                )
                db.session.add(new_transaction)
            
            db.session.commit()
            flash('Data restored successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Please upload a valid JSON backup file!', 'error')
    
    # Get list of existing backups
    backups = []
    if os.path.exists(backup_dir):
        for file in os.listdir(backup_dir):
            if file.endswith('.json') or file.endswith('.xlsx'):
                file_path = os.path.join(backup_dir, file)
                backups.append({
                    'name': file,
                    'size': f"{os.path.getsize(file_path) / 1024:.2f} KB",
                    'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return render_template('restore.html', backups=backups)

@app.route('/download_backup/<filename>')
def download_backup(filename):
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    backup_dir = 'backups'
    file_path = os.path.join(backup_dir, filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('File not found!', 'error')
        return redirect(url_for('restore'))

# ==================== EXPORT TO EXCEL ====================

@app.route('/export_data')
def export_data():
    if 'user_id' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()
    
    # Convert to list of dictionaries for pandas
    data = []
    for t in transactions:
        data.append({
            'Date': t.date.strftime('%Y-%m-%d'),
            'Type': t.type.upper(),
            'Category': t.category,
            'Description': t.description or '',
            'Amount (PKR)': t.amount
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Add summary sheet
        summary_data = {
            'Metric': ['Total Income (PKR)', 'Total Expense (PKR)', 'Net Balance (PKR)'],
            'Amount': [
                sum(t.amount for t in transactions if t.type == 'income'),
                sum(t.amount for t in transactions if t.type == 'expense'),
                sum(t.amount for t in transactions if t.type == 'income') - sum(t.amount for t in transactions if t.type == 'expense')
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    output.seek(0)
    
    # Send file to user
    return Response(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=finance_data.xlsx'}
    )

# ==================== RUN THE APP ====================

if __name__ == '__main__':
    app.run(debug=True)