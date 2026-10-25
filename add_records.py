from app import app, db, Transaction, User
from datetime import datetime

# Sample transactions data
transactions_data = [
    # January 2025
    {'type': 'income', 'amount': 85000, 'category': 'salary', 'description': 'Monthly Salary - January', 'date': '2025-01-01'},
    {'type': 'expense', 'amount': 25000, 'category': 'rent', 'description': 'House Rent', 'date': '2025-01-02'},
    {'type': 'expense', 'amount': 8000, 'category': 'bills', 'description': 'Electricity + Gas + Water', 'date': '2025-01-05'},
    {'type': 'expense', 'amount': 12000, 'category': 'food', 'description': 'Groceries and dining out', 'date': '2025-01-10'},
    {'type': 'expense', 'amount': 5000, 'category': 'transport', 'description': 'Fuel and public transport', 'date': '2025-01-12'},
    {'type': 'expense', 'amount': 7000, 'category': 'shopping', 'description': 'Clothes and accessories', 'date': '2025-01-15'},
    {'type': 'expense', 'amount': 4000, 'category': 'entertainment', 'description': 'Movies and outings', 'date': '2025-01-18'},
    {'type': 'expense', 'amount': 3000, 'category': 'health', 'description': 'Medicine and checkup', 'date': '2025-01-20'},
    {'type': 'expense', 'amount': 5000, 'category': 'food', 'description': 'Weekend groceries', 'date': '2025-01-25'},
    {'type': 'expense', 'amount': 7000, 'category': 'bills', 'description': 'Internet and phone bills', 'date': '2025-01-28'},
    
    # February 2025
    {'type': 'income', 'amount': 85000, 'category': 'salary', 'description': 'Monthly Salary - February', 'date': '2025-02-01'},
    {'type': 'expense', 'amount': 25000, 'category': 'rent', 'description': 'House Rent - February', 'date': '2025-02-02'},
    {'type': 'expense', 'amount': 7500, 'category': 'bills', 'description': 'Utilities - February', 'date': '2025-02-05'},
    {'type': 'expense', 'amount': 11000, 'category': 'food', 'description': 'Groceries February', 'date': '2025-02-10'},
    {'type': 'expense', 'amount': 5000, 'category': 'shopping', 'description': 'Home items', 'date': '2025-02-15'},
    {'type': 'expense', 'amount': 3500, 'category': 'transport', 'description': 'Fuel - February', 'date': '2025-02-20'},
    {'type': 'expense', 'amount': 4000, 'category': 'entertainment', 'description': 'Weekend trip', 'date': '2025-02-22'},
    
    # March 2025
    {'type': 'income', 'amount': 85000, 'category': 'salary', 'description': 'Monthly Salary - March', 'date': '2025-03-01'},
    {'type': 'expense', 'amount': 25000, 'category': 'rent', 'description': 'House Rent - March', 'date': '2025-03-02'},
    {'type': 'expense', 'amount': 8000, 'category': 'bills', 'description': 'Utilities - March', 'date': '2025-03-05'},
    {'type': 'expense', 'amount': 13000, 'category': 'food', 'description': 'Groceries + Dining March', 'date': '2025-03-10'},
    {'type': 'expense', 'amount': 6000, 'category': 'entertainment', 'description': 'Birthday celebration', 'date': '2025-03-15'},
    {'type': 'expense', 'amount': 4500, 'category': 'transport', 'description': 'Fuel - March', 'date': '2025-03-20'},
    {'type': 'expense', 'amount': 3500, 'category': 'health', 'description': 'Pharmacy', 'date': '2025-03-25'},
]

def add_sample_data():
    with app.app_context():
        # First, let's see existing users
        users = User.query.all()
        
        if not users:
            print("No users found! Please create a user first through the web interface.")
            print("Go to http://127.0.0.1:5000/register and create an account.")
            return
        
        print("\n📋 Available Users:")
        for user in users:
            print(f"  - ID: {user.id}, Username: {user.username}")
        
        # Ask which user to add data for
        user_id = input("\nEnter user ID to add transactions (usually 1 for first user): ")
        
        try:
            user_id = int(user_id)
            user = User.query.get(user_id)
            
            if not user:
                print(f"User with ID {user_id} not found!")
                return
            
            # Count existing transactions
            existing_count = Transaction.query.filter_by(user_id=user_id).count()
            print(f"\n📊 User '{user.username}' already has {existing_count} transactions.")
            
            confirm = input(f"\nAdd {len(transactions_data)} transactions for '{user.username}'? (yes/no): ")
            
            if confirm.lower() == 'yes':
                count = 0
                for data in transactions_data:
                    # Check if transaction already exists (simple check by date and amount)
                    existing = Transaction.query.filter_by(
                        user_id=user_id,
                        amount=data['amount'],
                        date=datetime.strptime(data['date'], '%Y-%m-%d')
                    ).first()
                    
                    if not existing:
                        transaction = Transaction(
                            user_id=user_id,
                            type=data['type'],
                            amount=data['amount'],
                            category=data['category'],
                            description=data['description'],
                            date=datetime.strptime(data['date'], '%Y-%m-%d')
                        )
                        db.session.add(transaction)
                        count += 1
                
                db.session.commit()
                print(f"\n✅ Successfully added {count} new transactions!")
                print(f"📊 Total transactions now: {Transaction.query.filter_by(user_id=user_id).count()}")
                
                # Show summary
                expenses = Transaction.query.filter_by(user_id=user_id, type='expense').count()
                income = Transaction.query.filter_by(user_id=user_id, type='income').count()
                print(f"\n📈 Summary for '{user.username}':")
                print(f"   - Income records: {income}")
                print(f"   - Expense records: {expenses}")
                print(f"   - Total records: {income + expenses}")
                
            else:
                print("Operation cancelled.")
                
        except ValueError:
            print("Invalid user ID! Please enter a number.")

if __name__ == '__main__':
    add_sample_data()python add_records.py