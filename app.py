import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, SelectMultipleField, DateField, SelectField
from wtforms.validators import DataRequired, NumberRange
from dotenv import load_dotenv
from news_fetcher import fetch_news
from datetime import datetime, timedelta
from flask_paginate import Pagination, get_page_parameter
from ExtractNews import start_news_extraction
from config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, asc, desc
import pytz
import requests
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
bootstrap = Bootstrap(app)

# Configure SQLAlchemy for the Max Pain database
max_pain_db_uri = app.config['MAX_PAIN_SQLALCHEMY_DATABASE_URI']
max_pain_engine = create_engine(max_pain_db_uri)
MaxPainSession = sessionmaker(bind=max_pain_engine)

# List of NSE stocks (you should replace this with a complete list)
NSE_STOCKS = [
    'RELIANCE', 'TCS', 'HDFC', 'INFY', 'ICICIBANK',
    'HDFCBANK', 'ITC', 'KOTAKBANK', 'LT', 'HINDUNILVR'
]

# List of available news sources
NEWS_SOURCES = [
    'Economic Times', 'Moneycontrol', 'LiveMint', 'Business Standard',
    'Financial Express', 'NDTV Profit', 'Bloomberg Quint'
]

# Models
class UserConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    risk_tolerance = db.Column(db.Float, nullable=False, default=0.5)
    investment_horizon = db.Column(db.String(50), nullable=False, default='Medium-term')
    preferred_sectors = db.Column(db.String(200), nullable=True)
    selected_stocks = db.Column(db.String(500), nullable=True)
    selected_news_sources = db.Column(db.String(200), nullable=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    config = db.relationship('UserConfig', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_config(self):
        if not self.config:
            self.config = UserConfig(user_id=self.id)
            db.session.add(self.config)
            db.session.commit()
        return self.config

# Forms
class ConfigForm(FlaskForm):
    risk_tolerance = FloatField('Risk Tolerance (0-1)', validators=[DataRequired(), NumberRange(min=0, max=1)])
    investment_horizon = StringField('Investment Horizon', validators=[DataRequired()])
    preferred_sectors = StringField('Preferred Sectors (comma-separated)')
    selected_stocks = SelectMultipleField('Select Stocks', choices=[(stock, stock) for stock in NSE_STOCKS])
    selected_news_sources = SelectMultipleField('Select News Sources', choices=[(source, source) for source in NEWS_SOURCES])
    submit = SubmitField('Update Configuration')

class NewsFilterForm(FlaskForm):
    date_from = DateField('From Date', default=lambda: datetime.now() - timedelta(days=7))
    date_to = DateField('To Date', default=datetime.now)
    sentiment = SelectField('Sentiment', choices=[
        ('', 'All Sentiments'),
        ('POSITIVE', 'Positive'),
        ('NEGATIVE', 'Negative'),
        ('NEUTRAL', 'Neutral')
    ])
    recommendation = SelectField('Recommendation', choices=[
        ('', 'All Recommendations'),
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold')
    ])
    stocks = SelectMultipleField('Stocks', choices=[(stock, stock) for stock in NSE_STOCKS])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html',bootstrap=bootstrap)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',bootstrap=bootstrap)

@app.route('/user_config', methods=['GET', 'POST'])
@login_required
def user_config():
    form = ConfigForm()
    user_config = current_user.get_config()
    
    if form.validate_on_submit():
        user_config.risk_tolerance = form.risk_tolerance.data
        user_config.investment_horizon = form.investment_horizon.data
        user_config.preferred_sectors = form.preferred_sectors.data
        user_config.selected_stocks = ','.join(form.selected_stocks.data)
        user_config.selected_news_sources = ','.join(form.selected_news_sources.data)
        db.session.commit()
        flash('Your configuration has been updated.', 'success')
        return redirect(url_for('user_config'))
    
    elif request.method == 'GET':
        form.risk_tolerance.data = user_config.risk_tolerance
        form.investment_horizon.data = user_config.investment_horizon
        form.preferred_sectors.data = user_config.preferred_sectors
        form.selected_stocks.data = user_config.selected_stocks.split(',') if user_config.selected_stocks else []
        form.selected_news_sources.data = user_config.selected_news_sources.split(',') if user_config.selected_news_sources else []
    
    return render_template('user_config.html', form=form,bootstrap=bootstrap)

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
    return render_template('login.html',bootstrap=bootstrap)

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
                       render_template('emails/welcome.html', user=new_user,bootstrap=bootstrap))
            
            return redirect(url_for('login'))
    
    return render_template('register.html',bootstrap=bootstrap)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('index'))
    pending_users = User.query.filter_by(is_approved=False).all()
    all_users = User.query.all()
    return render_template('admin.html', pending_users=pending_users, all_users=all_users,bootstrap=bootstrap)

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
               render_template('emails/approved.html', user=user,bootstrap=bootstrap))
    
    return redirect(url_for('admin'))

@app.route('/news', methods=['GET'])
@login_required
def news():
    # Get pagination parameters
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 21
    
    form = NewsFilterForm()
    
    # Get filter values from request args
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    sentiment = request.args.get('sentiment')
    recommendation = request.args.get('recommendation')
    selected_stocks = request.args.getlist('stocks')

    # Set form values from request args (same as before)
    if date_from:
        form.date_from.data = datetime.strptime(date_from, '%Y-%m-%d')
    if date_to:
        form.date_to.data = datetime.strptime(date_to, '%Y-%m-%d')
    if sentiment:
        form.sentiment.data = sentiment
    if recommendation:
        form.recommendation.data = recommendation
    if selected_stocks:
        form.stocks.data = selected_stocks
    elif not form.stocks.data:
        user_config = current_user.get_config()
        if user_config.selected_stocks:
            form.stocks.data = user_config.selected_stocks.split(',')

    # Build the SQL query dynamically
    query = """
        SELECT title, description, link, pubDate, sentiment, recommendation, stocks 
        FROM news_articles 
        WHERE 1=1 '
    """
    count_query = """
        SELECT COUNT(*) 
        FROM news_articles 
        WHERE 1=1 '
    """
    params = []

    # Add filters to both queries
    filter_conditions = []
    if form.date_from.data:
        filter_conditions.append("date(pubDate) >= date(?)")
        params.append(form.date_from.data.isoformat())
    if form.date_to.data:
        filter_conditions.append("date(pubDate) <= date(?)")
        params.append(form.date_to.data.isoformat())
    if form.sentiment.data:
        filter_conditions.append("sentiment = ?")
        params.append(form.sentiment.data)
    if form.recommendation.data:
        filter_conditions.append("recommendation = ?")
        params.append(form.recommendation.data)

    if filter_conditions:
        filter_sql = " AND " + " AND ".join(filter_conditions)
        query += filter_sql
        count_query += filter_sql

    # Add ordering and pagination
    query += " ORDER BY pubDate DESC LIMIT ? OFFSET ?"
    pagination_params = params.copy()
    pagination_params.extend([per_page, (page - 1) * per_page])

    # Connect to the database
    conn = sqlite3.connect('news_database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Get paginated results
    cursor.execute(query, pagination_params)
    articles = cursor.fetchall()
    conn.close()
    
    # Process the articles
    processed_articles = []
    selected_stocks = form.stocks.data if form.stocks.data else []
    
    for article in articles:
        try:
            pub_date = datetime.fromisoformat(article['pubDate'])
            formatted_date = pub_date.strftime('%B %d, %Y %I:%M %p')
            stocks = json.loads(article['stocks'])
            
            processed_articles.append({
                'title': article['title'],
                'description': article['description'],
                'link': article['link'],
                'pubDate': formatted_date,
                'sentiment': article['sentiment'],
                'recommendation': article['recommendation'],
                'stocks': stocks
            })
        except Exception as e:
            print(f"Error processing article: {e}")
            continue
    
    # Create pagination object
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5',
        record_name='articles'
    )
    
    return render_template(
        'news.html',
        articles=processed_articles,
        form=form,
        pagination=pagination,
        page=page,bootstrap=bootstrap
    )

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
                   render_template('emails/declined.html', user=user,bootstrap=bootstrap))
        
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
                   render_template('emails/account_removed.html', user=user,bootstrap=bootstrap))
        
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} has been removed from the system.', 'success')
    
    return redirect(url_for('admin'))

def send_email(to, subject, template):
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
    MAILGUN_FROM = os.getenv('MAILGUN_FROM')
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
                       render_template('emails/password_changed.html', user=current_user,bootstrap=bootstrap))
            
            return redirect(url_for('index'))
        else:
            flash('Incorrect old password.', 'error')
    return render_template('change_password.html',bootstrap=bootstrap)

@app.route('/max_pain', methods=['GET'])
def max_pain():
    # Get pagination parameters
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10

    # Get sorting parameters
    sort_by = request.args.get('sort_by', 'record_time')
    sort_order = request.args.get('sort_order', 'desc')

    # Get filter and search parameters
    search_query = request.args.getlist('search')

    # Fetch Max Pain data from the Max Pain database
    session = MaxPainSession()

    # Fetch unique index names for the dropdown
    unique_index_names = session.execute(text("SELECT DISTINCT index_name FROM max_pain_data")).fetchall()
    unique_index_names = [row[0] for row in unique_index_names]

    # Build the base query
    base_query = "SELECT * FROM max_pain_data WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM max_pain_data WHERE 1=1"
    params = {}

    if search_query:
        base_query += " AND index_name IN :search_query"
        count_query += " AND index_name IN :search_query"
        params['search_query'] = tuple(search_query)

    base_query += f" ORDER BY {sort_by} {sort_order} LIMIT :limit OFFSET :offset"
    params['limit'] = per_page
    params['offset'] = (page - 1) * per_page

    # Execute the count query
    total = session.execute(text(count_query), params).scalar()

    # Execute the base query with pagination
    result = session.execute(text(base_query), params).fetchall()

    # Convert rows to dictionaries and convert record_time to IST
    max_pain_data = []
    utc = pytz.utc
    ist = pytz.timezone('Asia/Kolkata')
    for row in result:
        row_dict = dict(row._mapping)
        if 'record_time' in row_dict:
            utc_time = utc.localize(row_dict['record_time'])
            ist_time = utc_time.astimezone(ist)
            row_dict['record_time'] = ist_time.strftime('%Y-%m-%d %H:%M:%S')
        max_pain_data.append(row_dict)
    session.close()

    # Create pagination object
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total,
        css_framework='bootstrap5',
        record_name='max_pain_data'
    )

    return render_template(
        'max_pain.html',
        max_pain_data=max_pain_data,
        pagination=pagination,
        sort_by=sort_by,
        sort_order=sort_order,
        search_query=search_query,
        unique_index_names=unique_index_names,bootstrap=bootstrap
    )

@app.route('/max_pain_new', methods=['GET'])
def max_pain_new():
    # Get pagination parameters
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 20

    # Get sorting parameters
    sort_by = request.args.get('sort_by', 'record_time')
    sort_order = request.args.get('sort_order', 'desc')

    # Get filter and search parameters
    index_name_filter = request.args.get('index_name', '')
    expiry_date_filter = request.args.get('expiry_date', '')

    # Fetch Max Pain data from the Max Pain database
    session = MaxPainSession()

    # Fetch unique index names for the tabs
    unique_index_names = session.execute(text("SELECT DISTINCT index_name FROM max_pain_data")).fetchall()
    unique_index_names = [row[0] for row in unique_index_names]

    # Fetch unique expiry dates for the selected index
    expiry_dates = []
    if index_name_filter:
        result = session.execute(text("SELECT DISTINCT expiry_date FROM max_pain_data WHERE index_name = :index_name ORDER BY expiry_date"), {'index_name': index_name_filter}).fetchall()
        expiry_dates = [row[0] for row in result]

    # Build the base query with filters
    base_query = "SELECT * FROM max_pain_data WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM max_pain_data WHERE 1=1"
    params = {}

    if index_name_filter:
        base_query += " AND index_name = :index_name"
        count_query += " AND index_name = :index_name"
        params['index_name'] = index_name_filter

    if expiry_date_filter:
        base_query += " AND expiry_date = :expiry_date"
        count_query += " AND expiry_date = :expiry_date"
        params['expiry_date'] = expiry_date_filter

    base_query += f" ORDER BY {sort_by} {sort_order} LIMIT :limit OFFSET :offset"
    params['limit'] = per_page
    params['offset'] = (page - 1) * per_page

    # Execute the count query with filters
    total_filtered = session.execute(text(count_query), params).scalar()

    # Execute the base query with pagination
    result = session.execute(text(base_query), params).fetchall()

    # Convert rows to dictionaries and convert record_time to IST
    max_pain_data = []
    utc = pytz.utc
    ist = pytz.timezone('Asia/Kolkata')
    for row in result:
        row_dict = dict(row._mapping)
        if 'record_time' in row_dict:
            utc_time = utc.localize(row_dict['record_time'])
            ist_time = utc_time.astimezone(ist)
            row_dict['record_time'] = ist_time.strftime('%Y-%m-%d %H:%M:%S')
        max_pain_data.append(row_dict)
    session.close()

    # Create pagination object
    pagination = Pagination(
        page=page,
        per_page=per_page,
        total=total_filtered,
        css_framework='bootstrap5',
        record_name='max_pain_data'
    )

    return render_template(
        'max_pain_new.html',
        max_pain_data=max_pain_data,
        pagination=pagination,
        sort_by=sort_by,
        sort_order=sort_order,
        index_name_filter=index_name_filter,
        expiry_date_filter=expiry_date_filter,
        unique_index_names=unique_index_names,
        expiry_dates=expiry_dates,
        total_filtered=total_filtered
    )

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

# Add this near the start of your app initialization
#news_thread = start_news_extraction()
#start_news_extraction()
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0',port=int(os.getenv('APP_PORT', 5000)))

