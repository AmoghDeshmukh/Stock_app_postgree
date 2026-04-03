from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
import os
import hashlib
import secrets

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'material_stock_secret_key_2024')

# Session configuration for Vercel (serverless)
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Handle PostgreSQL URL compatibility (postgres:// -> postgresql://)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///material_stock.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')  # Your email
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')  # Your app password
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@materialstock.com')

db = SQLAlchemy(app)
mail = Mail(app)

# Email sending function
def send_reset_email(user_email, reset_url):
    """Send password reset email"""
    try:
        msg = Message(
            subject='Password Reset Request - Material Stock Manager',
            recipients=[user_email],
            html=f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Material Stock Manager</h1>
                </div>
                <div style="padding: 30px; background: #f8f9fa;">
                    <h2 style="color: #333;">Password Reset Request</h2>
                    <p style="color: #666; line-height: 1.6;">
                        You have requested to reset your password. Click the button below to create a new password:
                    </p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                            Reset Password
                        </a>
                    </div>
                    <p style="color: #666; font-size: 14px;">
                        Or copy and paste this link in your browser:<br>
                        <a href="{reset_url}" style="color: #667eea; word-break: break-all;">{reset_url}</a>
                    </p>
                    <p style="color: #999; font-size: 12px; margin-top: 30px;">
                        This link will expire in 1 hour. If you didn't request this, please ignore this email.
                    </p>
                </div>
                <div style="padding: 20px; text-align: center; color: #999; font-size: 12px;">
                    &copy; 2026 Material Stock Management System
                </div>
            </div>
            '''
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # Email required for password recovery
    phone = db.Column(db.String(20), unique=True, nullable=True)  # Phone is optional
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='operator')  # 'admin', 'manager', 'operator'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete timestamp

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token
    
    def verify_reset_token(self):
        if self.reset_token and self.reset_token_expiry:
            return datetime.utcnow() < self.reset_token_expiry
        return False
    
    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expiry = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active
        }

# Material Model
class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    item_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=True, default='Category A')  # Category A, B, C, D
    party_name = db.Column(db.String(200), nullable=True, default='')
    inward = db.Column(db.Integer, nullable=False, default=0)
    outward = db.Column(db.Integer, nullable=False, default=0)
    balance = db.Column(db.Integer, nullable=False, default=0)
    storage_place = db.Column(db.String(200), nullable=True, default='')
    description = db.Column(db.Text, nullable=True, default='')  # Optional description field
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete timestamp
    deleted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Who deleted
    
    # Relationship to User
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('materials', lazy=True))
    deleter = db.relationship('User', foreign_keys=[deleted_by])

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d'),
            'item_name': self.item_name,
            'category': self.category or 'Category A',
            'party_name': self.party_name or '',
            'inward': self.inward,
            'outward': self.outward,
            'balance': self.balance,
            'storage_place': self.storage_place or '',
            'description': self.description or '',
            'user_id': self.user_id,
            'created_by': self.user.username if self.user else 'Unknown',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'deleted_at': self.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if self.deleted_at else None,
            'deleted_by': self.deleter.username if self.deleter else None
        }

# MaterialHistory Model - Track individual actions/transactions
class MaterialHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    action_number = db.Column(db.Integer, nullable=False, default=1)
    date = db.Column(db.Date, nullable=False)
    item_name = db.Column(db.String(200), nullable=True)  # Item name at this action
    party_name = db.Column(db.String(200), nullable=True)
    action_inward = db.Column(db.Integer, nullable=False, default=0)  # Inward for this action
    action_outward = db.Column(db.Integer, nullable=False, default=0)  # Outward for this action
    running_balance = db.Column(db.Integer, nullable=False, default=0)  # Balance after this action
    storage_place = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True, default='')  # Description for this action
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    material = db.relationship('Material', backref=db.backref('history', lazy=True, order_by='MaterialHistory.action_number.asc()', cascade='all, delete-orphan'))
    user = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'material_id': self.material_id,
            'action_number': self.action_number,
            'date': self.date.strftime('%Y-%m-%d'),
            'item_name': self.item_name or '',
            'party_name': self.party_name or '',
            'action_inward': self.action_inward,
            'action_outward': self.action_outward,
            'running_balance': self.running_balance,
            'storage_place': self.storage_place or '',
            'description': self.description or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': self.user.username if self.user else 'Unknown'
        }

# Create database tables
with app.app_context():
    db.create_all()
    
    # Migration: Add description column if it doesn't exist
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('material')]
    if 'description' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE material ADD COLUMN description TEXT DEFAULT ""'))
            conn.commit()
        print("Migration: Added 'description' column to material table")
    
    # Migration: Add description column to material_history if it doesn't exist
    history_columns = [col['name'] for col in inspector.get_columns('material_history')]
    if 'description' not in history_columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE material_history ADD COLUMN description TEXT DEFAULT ""'))
            conn.commit()
        print("Migration: Added 'description' column to material_history table")
    
    # Migration: Add category column to material if it doesn't exist
    if 'category' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE material ADD COLUMN category VARCHAR(50) DEFAULT "Category A"'))
            conn.commit()
        print("Migration: Added 'category' column to material table")
    
    # Migration: Add deleted_at column to material if it doesn't exist (soft delete)
    if 'deleted_at' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE material ADD COLUMN deleted_at DATETIME'))
            conn.commit()
        print("Migration: Added 'deleted_at' column to material table")
    
    # Migration: Add deleted_by column to material if it doesn't exist
    if 'deleted_by' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE material ADD COLUMN deleted_by INTEGER'))
            conn.commit()
        print("Migration: Added 'deleted_by' column to material table")

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Database initialization endpoint (for Vercel cold starts)
@app.route('/api/init-db')
def init_db():
    """Initialize database tables - useful for first deployment"""
    try:
        db.create_all()
        return jsonify({'success': True, 'message': 'Database tables created/verified'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Health check endpoint
@app.route('/api/health')
def health_check():
    """Check if app and database are working"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 500

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        data = request.form
        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Find user by username or email (exclude deleted users)
        user = User.query.filter(
            (User.username == username_or_email) |
            (User.email == username_or_email)
        ).filter(User.deleted_at == None).first()
        
        if user and user.check_password(password) and user.is_active:
            session.permanent = True  # Make session persist
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials or account inactive', 'error')
    
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Please enter your email address', 'error')
        else:
            user = User.query.filter_by(email=email).first()
            
            if user:
                # Generate reset token
                token = user.generate_reset_token()
                db.session.commit()
                
                reset_url = url_for('reset_password', token=token, _external=True)
                
                # Try to send email
                email_sent = send_reset_email(email, reset_url)
                
                if email_sent:
                    flash('Password reset link has been sent to your email!', 'success')
                    return render_template('forgot_password.html', email_sent=True, email=email)
                else:
                    # If email sending fails, show the link (fallback for demo)
                    flash('Email service unavailable. Use the link below to reset your password.', 'info')
                    return render_template('forgot_password.html', reset_link=reset_url, email=email)
            else:
                # Don't reveal if email exists or not for security
                flash('If an account with that email exists, a reset link has been sent.', 'info')
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.verify_reset_token():
        flash('Invalid or expired reset link. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            user.set_password(password)
            user.clear_reset_token()
            db.session.commit()
            flash('Your password has been reset successfully! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token, email=user.email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        data = request.form
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters')
        
        if not email:
            errors.append('Email address is required')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        # Check if username exists
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists')
        
        # Check if email exists
        if email and User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            try:
                # Make 'amogh' username an admin by default
                role = 'admin' if username.lower() == 'amogh' else 'operator'
                user = User(username=username, email=email, role=role)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Registration failed: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Profile Routes
@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user = User.query.get(session['user_id'])
    data = request.form
    
    errors = []
    
    # Get form data
    new_username = data.get('username', '').strip()
    new_email = data.get('email', '').strip() or None
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    # Validate username
    if new_username and new_username != user.username:
        if len(new_username) < 3:
            errors.append('Username must be at least 3 characters')
        elif User.query.filter(User.username == new_username, User.id != user.id).first():
            errors.append('Username already exists')
        else:
            user.username = new_username
            session['username'] = new_username
    
    # Validate email
    if new_email and new_email != user.email:
        if User.query.filter(User.email == new_email, User.id != user.id).first():
            errors.append('Email already registered')
        else:
            user.email = new_email
    elif not new_email:
        errors.append('Email address is required')
    
    # Password change (optional)
    if new_password:
        if not current_password:
            errors.append('Current password is required to change password')
        elif not user.check_password(current_password):
            errors.append('Current password is incorrect')
        elif len(new_password) < 6:
            errors.append('New password must be at least 6 characters')
        elif new_password != confirm_password:
            errors.append('New passwords do not match')
        else:
            user.set_password(new_password)
    
    if errors:
        for error in errors:
            flash(error, 'error')
    else:
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    return redirect(url_for('profile'))

@app.route('/profile/delete')
@login_required
def delete_account():
    user = User.query.get(session['user_id'])
    
    try:
        # Soft delete - set deleted_at timestamp instead of actually deleting
        user.deleted_at = datetime.utcnow()
        user.is_active = False
        db.session.commit()
        session.clear()
        flash('Your account has been deleted successfully. Contact admin to recover.', 'info')
        return redirect(url_for('login'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'error')
        return redirect(url_for('profile'))

# Admin Routes - User Management
@app.route('/admin/users')
@admin_required
def admin_users():
    """View all users (Admin only)"""
    # Active users (not deleted)
    users = User.query.filter(User.deleted_at == None).order_by(User.created_at.desc()).all()
    # Deleted users for recovery
    deleted_users = User.query.filter(User.deleted_at != None).order_by(User.deleted_at.desc()).all()
    return render_template('admin_users.html', users=users, deleted_users=deleted_users)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    """Edit a user's profile (Admin only)"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        data = request.form
        errors = []
        
        new_username = data.get('username', '').strip()
        new_email = data.get('email', '').strip()
        new_role = data.get('role', 'operator')
        new_password = data.get('new_password', '')
        is_active = data.get('is_active') == 'on'
        
        # Validate username
        if new_username and new_username != user.username:
            if len(new_username) < 3:
                errors.append('Username must be at least 3 characters')
            elif User.query.filter(User.username == new_username, User.id != user.id).first():
                errors.append('Username already exists')
            else:
                user.username = new_username
        
        # Validate email
        if new_email and new_email != user.email:
            if User.query.filter(User.email == new_email, User.id != user.id).first():
                errors.append('Email already registered')
            else:
                user.email = new_email
        elif not new_email:
            errors.append('Email is required')
        
        # Update role
        if new_role in ['admin', 'manager', 'operator']:
            user.role = new_role
        
        # Update active status
        user.is_active = is_active
        
        # Password change (optional)
        if new_password:
            if len(new_password) < 6:
                errors.append('Password must be at least 6 characters')
            else:
                user.set_password(new_password)
        
        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            try:
                db.session.commit()
                flash(f'User {user.username} updated successfully!', 'success')
                return redirect(url_for('admin_users'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('admin_edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Soft delete a user (Admin only)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == session['user_id']:
        flash('You cannot delete your own account from admin panel', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        username = user.username
        # Soft delete - set deleted_at timestamp
        user.deleted_at = datetime.utcnow()
        user.is_active = False
        db.session.commit()
        flash(f'User {username} has been deleted (can be recovered)', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/recover', methods=['POST'])
@admin_required
def admin_recover_user(user_id):
    """Recover a soft-deleted user (Admin only)"""
    user = User.query.get_or_404(user_id)
    
    if user.deleted_at is None:
        flash('User is not deleted', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        username = user.username
        user.deleted_at = None
        user.is_active = True
        db.session.commit()
        flash(f'User {username} has been recovered successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recovering user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/permanent-delete', methods=['POST'])
@admin_required
def admin_permanent_delete_user(user_id):
    """Permanently delete a user (Admin only)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == session['user_id']:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin_users'))
    
    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f'User {username} has been permanently deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def admin_toggle_user_status(user_id):
    """Toggle user active status (Admin only)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user.id == session['user_id']:
        flash('You cannot deactivate your own account', 'error')
        return redirect(url_for('admin_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} has been {status}', 'success')
    return redirect(url_for('admin_users'))

# Admin Backup & Restore Routes
@app.route('/admin/backup')
@admin_required
def admin_backup():
    """Admin backup page - view deleted items and download database"""
    # Get deleted materials
    deleted_materials = Material.query.filter(Material.deleted_at != None).order_by(Material.deleted_at.desc()).all()
    
    # Get deleted users
    deleted_users = User.query.filter(User.deleted_at != None).order_by(User.deleted_at.desc()).all()
    
    # Get stats
    stats = {
        'total_users': User.query.filter(User.deleted_at == None).count(),
        'total_materials': Material.query.filter(Material.deleted_at == None).count(),
        'deleted_users': len(deleted_users),
        'deleted_materials': len(deleted_materials),
        'total_history': MaterialHistory.query.count()
    }
    
    return render_template('admin_backup.html', 
                          deleted_materials=deleted_materials, 
                          deleted_users=deleted_users,
                          stats=stats)

@app.route('/admin/materials/<int:material_id>/restore', methods=['POST'])
@admin_required
def admin_restore_material(material_id):
    """Restore a soft-deleted material (Admin only)"""
    material = Material.query.get_or_404(material_id)
    
    if material.deleted_at is None:
        flash('Material is not deleted', 'error')
        return redirect(url_for('admin_backup'))
    
    try:
        item_name = material.item_name
        material.deleted_at = None
        material.deleted_by = None
        db.session.commit()
        flash(f'Material "{item_name}" has been restored successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error restoring material: {str(e)}', 'error')
    
    return redirect(url_for('admin_backup'))

@app.route('/admin/materials/<int:material_id>/permanent-delete', methods=['POST'])
@admin_required
def admin_permanent_delete_material(material_id):
    """Permanently delete a material and its history (Admin only)"""
    material = Material.query.get_or_404(material_id)
    
    try:
        item_name = material.item_name
        # Delete associated history records first
        MaterialHistory.query.filter_by(material_id=material_id).delete()
        db.session.delete(material)
        db.session.commit()
        flash(f'Material "{item_name}" has been permanently deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting material: {str(e)}', 'error')
    
    return redirect(url_for('admin_backup'))

@app.route('/admin/download-backup')
@admin_required
def download_backup():
    """Download SQLite database backup"""
    import shutil
    from flask import send_file
    
    # Create backup filename with timestamp
    backup_filename = f'material_stock_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    # Get the database path
    db_path = os.path.join(app.instance_path, 'material_stock.db')
    
    if os.path.exists(db_path):
        return send_file(
            db_path,
            as_attachment=True,
            download_name=backup_filename,
            mimetype='application/x-sqlite3'
        )
    else:
        flash('Database file not found', 'error')
        return redirect(url_for('admin_backup'))

@app.route('/admin/export-json')
@admin_required
def export_json():
    """Export all data as JSON backup"""
    import json
    from flask import Response
    
    # Get all data
    users = User.query.all()
    materials = Material.query.all()
    history = MaterialHistory.query.all()
    
    backup_data = {
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'users': [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'deleted_at': u.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if u.deleted_at else None
        } for u in users],
        'materials': [m.to_dict() for m in materials],
        'history': [h.to_dict() for h in history]
    }
    
    json_data = json.dumps(backup_data, indent=2)
    filename = f'material_stock_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    return Response(
        json_data,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )

@app.route('/admin/import-json', methods=['POST'])
@admin_required
def import_json_preview():
    """Upload JSON backup and preview contents for selective import"""
    import json
    
    if 'backup_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('admin_backup'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_backup'))
    
    if not file.filename.endswith('.json'):
        flash('Please upload a JSON file', 'error')
        return redirect(url_for('admin_backup'))
    
    try:
        content = file.read().decode('utf-8')
        backup_data = json.loads(content)
        
        # Store in session for the import step
        session['import_data'] = backup_data
        
        # Get current ACTIVE items for comparison (exclude deleted)
        existing_material_names = [m.item_name.lower() for m in Material.query.filter(Material.deleted_at == None).all()]
        existing_usernames = [u.username.lower() for u in User.query.filter(User.deleted_at == None).all()]
        
        # Mark which items already exist (only active ones)
        for m in backup_data.get('materials', []):
            m['exists'] = m['item_name'].lower() in existing_material_names
        
        for u in backup_data.get('users', []):
            u['exists'] = u['username'].lower() in existing_usernames
        
        return render_template('admin_import_preview.html', 
                              backup_data=backup_data,
                              existing_materials=len(existing_material_names),
                              existing_users=len(existing_usernames))
    
    except json.JSONDecodeError:
        flash('Invalid JSON file', 'error')
        return redirect(url_for('admin_backup'))
    except Exception as e:
        flash(f'Error reading file: {str(e)}', 'error')
        return redirect(url_for('admin_backup'))

@app.route('/admin/import-materials', methods=['POST'])
@admin_required
def import_materials():
    """Import selected materials from uploaded JSON backup"""
    import json
    
    backup_data = session.get('import_data')
    if not backup_data:
        flash('No import data found. Please upload a file first.', 'error')
        return redirect(url_for('admin_backup'))
    
    selected_ids = request.form.getlist('material_ids')
    if not selected_ids:
        flash('No materials selected for import', 'warning')
        return redirect(url_for('admin_backup'))
    
    selected_ids = [int(id) for id in selected_ids]
    imported_count = 0
    skipped_count = 0
    
    try:
        for material_data in backup_data.get('materials', []):
            if material_data['id'] in selected_ids:
                # Check if item name already exists
                existing = Material.query.filter(
                    db.func.lower(Material.item_name) == material_data['item_name'].lower(),
                    Material.deleted_at == None
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create new material
                new_material = Material(
                    date=datetime.strptime(material_data['date'], '%Y-%m-%d').date(),
                    item_name=material_data['item_name'],
                    category=material_data.get('category', 'Split AC'),
                    party_name=material_data.get('party_name', ''),
                    inward=material_data.get('inward', 0),
                    outward=material_data.get('outward', 0),
                    balance=material_data.get('balance', 0),
                    storage_place=material_data.get('storage_place', ''),
                    description=material_data.get('description', ''),
                    user_id=session['user_id']  # Assign to current admin
                )
                db.session.add(new_material)
                imported_count += 1
        
        db.session.commit()
        
        # Clear session data
        session.pop('import_data', None)
        
        if imported_count > 0:
            flash(f'Successfully imported {imported_count} materials!', 'success')
        if skipped_count > 0:
            flash(f'Skipped {skipped_count} materials (already exist)', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing materials: {str(e)}', 'error')
    
    return redirect(url_for('admin_backup'))

# Routes
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/material-list')
@login_required
def material_list():
    """Material list page with simplified view (date, item name, total)"""
    return render_template('material_list.html')

# API Routes
@app.route('/api/materials', methods=['GET'])
@login_required
def get_materials():
    """Get materials - Admin sees all, others see only their own (excluding deleted)"""
    if session.get('role') == 'admin':
        materials = Material.query.filter(Material.deleted_at == None).order_by(Material.date.desc()).all()
    else:
        materials = Material.query.filter(
            Material.user_id == session['user_id'],
            Material.deleted_at == None
        ).order_by(Material.date.desc()).all()
    return jsonify([material.to_dict() for material in materials])

@app.route('/api/materials/<int:id>', methods=['GET'])
@login_required
def get_material(id):
    """Get a single material by ID - only if owner or admin"""
    material = Material.query.get_or_404(id)
    if session.get('role') != 'admin' and material.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    return jsonify(material.to_dict())

@app.route('/api/materials', methods=['POST'])
@login_required
def add_material():
    """Add a new material"""
    data = request.get_json()
    
    try:
        # Check for duplicate item name
        item_name = data['item_name'].strip()
        existing = Material.query.filter(
            Material.user_id == session['user_id'],
            Material.deleted_at == None,
            db.func.lower(Material.item_name) == item_name.lower()
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'message': f'Material with name "{item_name}" already exists. Please use a unique name.'
            }), 400
        
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        inward = int(data.get('inward', 0))
        outward = int(data.get('outward', 0))
        balance = inward - outward
        
        new_material = Material(
            date=date,
            item_name=item_name,
            category=data.get('category', 'Category A'),
            party_name=data.get('party_name', ''),
            inward=inward,
            outward=outward,
            balance=balance,
            storage_place=data.get('storage_place', ''),
            description=data.get('description', ''),
            user_id=session['user_id']
        )
        
        db.session.add(new_material)
        db.session.flush()  # Get the ID before committing
        
        # Record the first action in history
        first_action = MaterialHistory(
            material_id=new_material.id,
            action_number=1,
            date=date,
            item_name=data['item_name'],
            party_name=data.get('party_name', ''),
            action_inward=inward,
            action_outward=outward,
            running_balance=balance,
            storage_place=data.get('storage_place', ''),
            description=data.get('description', ''),
            created_by=session['user_id']
        )
        db.session.add(first_action)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Material added successfully!',
            'material': new_material.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error adding material: {str(e)}'
        }), 400

@app.route('/api/materials/<int:id>', methods=['PUT'])
@login_required
def update_material(id):
    """Update an existing material - only if owner or admin"""
    material = Material.query.get_or_404(id)
    
    # Check ownership
    if session.get('role') != 'admin' and material.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    data = request.get_json()
    
    try:
        # Check for duplicate item name (excluding current material and soft-deleted)
        new_item_name = data.get('item_name', '').strip()
        if new_item_name:
            existing = Material.query.filter(
                Material.user_id == material.user_id,
                Material.id != id,
                Material.deleted_at == None,
                db.func.lower(Material.item_name) == new_item_name.lower()
            ).first()
            
            if existing:
                return jsonify({
                    'success': False,
                    'message': f'Material with name "{new_item_name}" already exists. Please use a unique name.'
                }), 400
        
        # Get the action values (what to ADD)
        action_inward = int(data.get('action_inward', 0))
        action_outward = int(data.get('action_outward', 0))
        new_party_name = data.get('party_name', '')
        new_storage_place = data.get('storage_place', '')
        new_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        new_description = data.get('description', '')
        
        # Calculate new cumulative totals
        new_total_inward = material.inward + action_inward
        new_total_outward = material.outward + action_outward
        new_balance = new_total_inward - new_total_outward
        
        # Check if any tracked fields changed
        has_quantity_change = action_inward > 0 or action_outward > 0
        has_field_change = (
            new_party_name != (material.party_name or '') or
            new_storage_place != (material.storage_place or '') or
            new_description != (material.description or '')
        )
        
        # Record history if there's a quantity change OR any tracked field changed
        if has_quantity_change or has_field_change:
            # Get the next action number
            last_action = MaterialHistory.query.filter_by(material_id=material.id).order_by(MaterialHistory.action_number.desc()).first()
            next_action_number = (last_action.action_number + 1) if last_action else 2  # First action is the initial creation
            
            # Record this action in history
            history = MaterialHistory(
                material_id=material.id,
                action_number=next_action_number,
                date=new_date,
                item_name=new_item_name,
                party_name=new_party_name,
                action_inward=action_inward,
                action_outward=action_outward,
                running_balance=new_balance,
                storage_place=new_storage_place,
                description=new_description,
                created_by=session['user_id']
            )
            db.session.add(history)
        
        # Update material with cumulative totals
        material.date = new_date
        material.item_name = new_item_name
        if 'category' in data:
            material.category = data.get('category', material.category)
        material.party_name = new_party_name
        material.inward = new_total_inward
        material.outward = new_total_outward
        material.balance = new_balance
        material.storage_place = new_storage_place
        material.description = data.get('description', material.description or '')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Material updated successfully!',
            'material': material.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating material: {str(e)}'
        }), 400

@app.route('/api/materials/<int:id>/history', methods=['GET'])
@login_required
def get_material_history(id):
    """Get history of changes for a material"""
    material = Material.query.get_or_404(id)
    
    # Check ownership
    if session.get('role') != 'admin' and material.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    history = MaterialHistory.query.filter_by(material_id=id).order_by(MaterialHistory.action_number.asc()).all()
    return jsonify([h.to_dict() for h in history])

@app.route('/api/materials/<int:material_id>/history/<int:history_id>', methods=['DELETE'])
@login_required
def delete_history_entry(material_id, history_id):
    """Delete a single history entry"""
    material = Material.query.get_or_404(material_id)
    
    # Check ownership
    if session.get('role') != 'admin' and material.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    try:
        history = MaterialHistory.query.filter_by(id=history_id, material_id=material_id).first()
        if not history:
            return jsonify({'success': False, 'message': 'History entry not found'}), 404
        
        db.session.delete(history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'History entry deleted successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error deleting history: {str(e)}'
        }), 400

@app.route('/api/materials/<int:material_id>/history', methods=['DELETE'])
@login_required
def delete_all_history(material_id):
    """Delete all history for a material"""
    material = Material.query.get_or_404(material_id)
    
    # Check ownership
    if session.get('role') != 'admin' and material.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    try:
        count = MaterialHistory.query.filter_by(material_id=material_id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {count} history entries successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error deleting history: {str(e)}'
        }), 400

@app.route('/api/materials/<int:id>', methods=['DELETE'])
@login_required
def delete_material(id):
    """Soft delete a material - only if owner or admin"""
    material = Material.query.get_or_404(id)
    
    # Check ownership
    if session.get('role') != 'admin' and material.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    try:
        # Soft delete - set deleted_at timestamp
        material.deleted_at = datetime.utcnow()
        material.deleted_by = session['user_id']
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Material deleted successfully! Admin can restore if needed.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error deleting material: {str(e)}'
        }), 400

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Get statistics for dashboard - filtered by user unless admin (excluding deleted)"""
    if session.get('role') == 'admin':
        base_query = Material.query.filter(Material.deleted_at == None)
    else:
        base_query = Material.query.filter(Material.user_id == session['user_id'], Material.deleted_at == None)
    
    total_items = base_query.count()
    total_inward = db.session.query(db.func.sum(Material.inward)).filter(
        Material.deleted_at == None,
        Material.user_id == session['user_id'] if session.get('role') != 'admin' else True
    ).scalar() or 0
    total_outward = db.session.query(db.func.sum(Material.outward)).filter(
        Material.deleted_at == None,
        Material.user_id == session['user_id'] if session.get('role') != 'admin' else True
    ).scalar() or 0
    total_balance = db.session.query(db.func.sum(Material.balance)).filter(
        Material.deleted_at == None,
        Material.user_id == session['user_id'] if session.get('role') != 'admin' else True
    ).scalar() or 0
    
    # Get unique storage places count
    if session.get('role') == 'admin':
        storage_places = db.session.query(Material.storage_place).filter(Material.deleted_at == None).distinct().count()
    else:
        storage_places = db.session.query(Material.storage_place).filter(
            Material.user_id == session['user_id'], Material.deleted_at == None
        ).distinct().count()
    
    return jsonify({
        'total_items': total_items,
        'total_inward': total_inward,
        'total_outward': total_outward,
        'total_balance': total_balance,
        'storage_places': storage_places
    })

@app.route('/api/search', methods=['GET'])
@login_required
def search_materials():
    """Search materials by item name, party name, or storage place - filtered by user (excluding deleted)"""
    query = request.args.get('q', '')
    
    # Base filter - always exclude deleted
    if session.get('role') == 'admin':
        base_filter = Material.deleted_at == None
    else:
        base_filter = db.and_(Material.user_id == session['user_id'], Material.deleted_at == None)
    
    if query:
        materials = Material.query.filter(
            base_filter,
            (Material.item_name.ilike(f'%{query}%')) |
            (Material.party_name.ilike(f'%{query}%')) |
            (Material.storage_place.ilike(f'%{query}%'))
        ).order_by(Material.date.desc()).all()
    else:
        if session.get('role') == 'admin':
            materials = Material.query.filter(Material.deleted_at == None).order_by(Material.date.desc()).all()
        else:
            materials = Material.query.filter(
                Material.user_id == session['user_id'],
                Material.deleted_at == None
            ).order_by(Material.date.desc()).all()
    
    return jsonify([material.to_dict() for material in materials])

@app.route('/api/suggestions', methods=['GET'])
@login_required
def get_suggestions():
    """Get unique values for autocomplete suggestions - filtered by user (excluding deleted)"""
    if session.get('role') == 'admin':
        item_names = db.session.query(Material.item_name).filter(Material.deleted_at == None).distinct().all()
        party_names = db.session.query(Material.party_name).filter(Material.deleted_at == None).distinct().all()
        storage_places = db.session.query(Material.storage_place).filter(Material.deleted_at == None).distinct().all()
    else:
        item_names = db.session.query(Material.item_name).filter(
            Material.user_id == session['user_id'], Material.deleted_at == None
        ).distinct().all()
        party_names = db.session.query(Material.party_name).filter(
            Material.user_id == session['user_id'], Material.deleted_at == None
        ).distinct().all()
        storage_places = db.session.query(Material.storage_place).filter(
            Material.user_id == session['user_id'], Material.deleted_at == None
        ).distinct().all()
    
    return jsonify({
        'item_names': sorted([i[0] for i in item_names if i[0]]),
        'party_names': sorted([p[0] for p in party_names if p[0]]),
        'storage_places': sorted([s[0] for s in storage_places if s[0]])
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
