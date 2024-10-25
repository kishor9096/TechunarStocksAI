from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap5
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mailgun configuration
MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
MAILGUN_FROM = f"Your App <mailgun@{MAILGUN_DOMAIN}>"

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
bootstrap = Bootstrap5(app)

# Define a simple model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.is_approved:
                login_user(user)
                flash('Logged in successfully.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Your account is pending approval.', 'warning')
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
        else:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful. Please wait for admin approval.', 'success')
            
            # Send welcome email
            send_email(new_user.email, 'Welcome to Our App',
                       render_template('emails/welcome.html', user=new_user))
            
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('index'))
    pending_users = User.query.filter_by(is_approved=False).all()
    all_users = User.query.all()
    return render_template('admin.html', pending_users=pending_users, all_users=all_users)

@app.route('/approve/<int:user_id>')
@login_required
def approve_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'User {user.username} has been approved.', 'success')
    
    # Send approval email
    send_email(user.email, 'Your Account Has Been Approved',
               render_template('emails/approved.html', user=user))
    
    return redirect(url_for('admin'))

@app.route('/protected')
@login_required
def protected():
    return f'Hello, {current_user.username}! This is a protected page.'

@app.route('/decline_user/<int:user_id>')
@login_required
def decline_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.is_approved:
        flash('This user has already been approved.', 'warning')
    else:
        # Send decline email
        send_email(user.email, 'Your Account Registration Was Declined',
                   render_template('emails/declined.html', user=user))
        
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} has been declined and removed from the system.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/remove_user/<int:user_id>')
@login_required
def remove_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot remove an admin user.', 'warning')
    else:
        # Send removal notification email
        send_email(user.email, 'Your Account Has Been Removed',
                   render_template('emails/account_removed.html', user=user))
        
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} has been removed from the system.', 'success')
    
    return redirect(url_for('admin'))

def send_email(to, subject, template):
    return requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={"from": MAILGUN_FROM,
              "to": to,
              "subject": subject,
              "html": template})

# Add a route for password change
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        if current_user.check_password(old_password):
            current_user.set_password(new_password)
            db.session.commit()
            flash('Your password has been updated.', 'success')
            
            # Send password change alert
            send_email(current_user.email, 'Password Change Alert',
                       render_template('emails/password_changed.html', user=current_user))
            
            return redirect(url_for('index'))
        else:
            flash('Incorrect old password.', 'error')
    return render_template('change_password.html')

# Create the database tables
with app.app_context():
    db.create_all()
    # Create an admin user if it doesn't exist
    admin = User.query.filter_by(username=os.getenv('ADMIN_USERNAME')).first()
    if not admin:
        admin = User(
            username=os.getenv('ADMIN_USERNAME'),
            email=os.getenv('ADMIN_EMAIL'),
            is_approved=True,
            is_admin=True
        )
        admin.set_password(os.getenv('ADMIN_PASSWORD'))
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created.")
    else:
        print("Admin user already exists.")

if __name__ == '__main__':
    app.run(debug=False)  # Set debug to False in production
