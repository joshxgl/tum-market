from flask import Flask, request, jsonify, send_from_directory, session
from typing import List
import smtplib
import traceback
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_sqlalchemy import SQLAlchemy
import os
import re
import json
from dotenv import load_dotenv
import click
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import cloudinary
import cloudinary.uploader
from google import genai
from google.genai import types
from pydantic import BaseModel
from functools import wraps
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
if load_dotenv():
    print("✅ .env file detected and loaded.")
else:
    # This is common in production (Render/Railway) where vars are set in the dashboard
    print("ℹ️ No .env file found. Falling back to system environment variables.")

app = Flask(__name__)
app.url_map.strict_slashes = False  # Best practice: Treat /api/route and /api/route/ the same
app.secret_key = os.environ.get('SECRET_KEY', 'tum_market_secret')

# --- Gemini Matchmaking Models & Client ---
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None
    if not os.environ.get('RENDER'):
        print("⚠️ WARNING: GEMINI_API_KEY is missing. Matchmaking features will be disabled.")

class TakerMatch(BaseModel):
    talent_id: int
    phone_number: str
    email: str

class MatchmakerPayload(BaseModel):
    matches: List[TakerMatch]

# Increase max content length to allow for base64 image uploads (16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- Helpers & Decorators ---

def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"success": False, "message": "Unauthorized. Please log in first."}), 401
        return f(*args, **kwargs)
    return decorated_function

def not_suspended(f):
    """Decorator to block suspended users from accessing certain features."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if user_id:
            user = db.session.get(User, user_id)
            if user and user.is_suspended:
                return jsonify({"success": False, "message": "Your account has been suspended for violating marketplace rules."}), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to protect routes requiring admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = db.session.get(User, session.get('user_id'))
        if not user or not getattr(user, 'is_admin', False):
            return jsonify({"success": False, "message": "Access denied. Admin privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function

def upload_image_to_cloudinary(image_data, folder="tum_market/general"):
    """Helper to handle base64 image uploads to Cloudinary."""
    if not image_data or not image_data.startswith('data:image/'):
        return None
        
    try:
        # Check size if needed (approx 5MB check was in profile route)
        if len(image_data) > 7_000_000:
            raise ValueError("Image is too large (max 5MB).")
            
        # Use Cloudinary's built-in optimization: f_auto (format) and q_auto (quality)
        upload_result = cloudinary.uploader.upload(
            image_data, 
            folder=folder,
            fetch_format="auto",
            quality="auto"
        )
        return upload_result.get('secure_url')
    except Exception as e:
        app.logger.error(f"Cloudinary Upload Error: {str(e)}")
        # Re-raising allows the route to handle specific error messages
        raise e

def send_email(to_email, subject, text_body, html_body=None):
    """Utility to send emails using standard smtplib."""
    mail_server = os.environ.get('MAIL_SERVER')
    mail_port = os.environ.get('MAIL_PORT', 587)
    mail_user = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')

    if not all([mail_server, mail_user, mail_password]):
        return False

    msg = MIMEMultipart()
    msg['From'] = mail_user
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(text_body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(mail_server, int(mail_port))
        server.starttls()
        server.login(mail_user, mail_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

# Best Practice: Identify users by ID if logged in, otherwise by IP
def get_user_identifier():
    if 'user_id' in session:
        return str(session['user_id'])
    return get_remote_address()

# Rate Limiter Setup
limiter = Limiter(
    key_func=get_user_identifier,
    app=app,
    # Best Practice: Use Redis in production. Fallback to memory for local dev.
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
    default_limits=["500 per hour", "100 per minute"],
    strategy="fixed-window",
)

# Global handler to ensure all 405 errors return JSON instead of HTML
@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({
        "success": False, 
        "message": "Method not allowed for this endpoint. Ensure you are using the correct HTTP method (e.g., POST)."
    }), 405

# Best Practice: Return JSON errors for Rate Limits
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "success": False, 
        "message": f"Too many requests. Please try again in a moment. {e.description}"
    }), 429

# Database Configuration
def get_database_uri():
    """
    Standardizes the DATABASE_URL for SQLAlchemy and provides a local fallback.
    Fixes the 'postgres://' vs 'postgresql://' incompatibility.
    """
    uri = os.environ.get('DATABASE_URL')
    
    # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)

    # Detect Render Internal URL used locally
    # This check ensures that if we're running locally (not on Render) and the URI
    # looks like a Render internal one (dpg- but no .render.com), we warn and fallback.
    if uri and "dpg-" in uri and ".render.com" not in uri and os.environ.get('RENDER') != 'true':
        print("\n" + "!" * 60)
        print("⚠️  DATABASE CONFIGURATION ERROR:")
        print("   You are using a Render INTERNAL Database URL on a local machine.")
        print("   Please use the EXTERNAL Database URL from your Render dashboard.")
        print("   Falling back to local SQLite for safety.")
        print("!" * 60 + "\n")
        # Force fallback to SQLite by returning the SQLite URI immediately
        return 'sqlite:///tum_market.db'

    return uri or 'sqlite:///tum_market.db'

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
print(f"DEBUG: Final SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}") # Added for debugging
db = SQLAlchemy(app)

# Cloudinary configuration
if os.environ.get('CLOUDINARY_URL'):
    # This automatically parses the CLOUDINARY_URL environment variable
    cloudinary.config(secure=True)
else:
    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key = os.environ.get('CLOUDINARY_API_KEY'),
        api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
        secure = True
    )

STATIC_FOLDER = 'static'

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    profile_picture = db.Column(db.Text, nullable=True)
    listings = db.relationship('Listing', backref='author', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='recipient', lazy=True, cascade="all, delete-orphan")
    is_subscribed = db.Column(db.Boolean, default=True)
    subscription_updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_skill_verified = db.Column(db.Boolean, default=False)
    phone_number = db.Column(db.String(20), nullable=True)
    skills = db.Column(db.Text, nullable=True) # Comma-separated skills
    verified_skills = db.Column(db.Text, nullable=True) # Comma-separated verified skills
    resume_url = db.Column(db.Text, nullable=True)
    verification_status = db.Column(db.String(20), default='none') # none, pending, verified
    is_suspended = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)



class JobPosting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    budget = db.Column(db.String(100))
    skills = db.Column(db.Text) # Comma-separated tags
    posted_by = db.Column(db.String(100), nullable=False)
    client_name = db.Column(db.String(100), nullable=False) # New field
    client_contact = db.Column(db.String(100), nullable=False) # New field
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    verified_client = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='active', index=True)

class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_posting.id', ondelete='CASCADE'), nullable=False)
    talent_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='pending')
    __table_args__ = (db.UniqueConstraint('job_id', 'talent_id', name='_job_talent_uc'),)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_posting.id', ondelete='CASCADE'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True) # pending, reviewed, dismissed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Appeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_posting.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True) # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True) # Optimized search
    price = db.Column(db.Float, nullable=False, index=True) # Optimized sorting
    location = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True) # Optimized filtering
    image = db.Column(db.Text, nullable=True)
    seller_phone = db.Column(db.String(20), nullable=False)
    posted_by = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True) # Optimized user profile
    status = db.Column(db.String(20), default='available', index=True)
    tier = db.Column(db.String(20), default='free', index=True)
    date_posted = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    views = db.Column(db.Integer, default=0)
    view_history = db.relationship('ListingView', backref='listing', lazy=True, cascade="all, delete-orphan")

class ListingView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=True, index=True)
    type = db.Column(db.String(50))
    title = db.Column(db.String(100))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

with app.app_context():
    db.create_all()
    
    # Store IntaSend Keys in app config so they are accessible in routes
    app.config['INTASEND_PUBLISHABLE_KEY'] = os.environ.get('INTASEND_PUBLISHABLE_KEY')
    app.config['INTASEND_SECRET_KEY'] = os.environ.get('INTASEND_SECRET_KEY')
    
    if not all([app.config['INTASEND_PUBLISHABLE_KEY'], app.config['INTASEND_SECRET_KEY']]):
        if not app.debug:
            # In production, we should know if billing is broken immediately
            app.logger.critical("🚨 CRITICAL: IntaSend API keys are missing from environment!")
        else:
            print("🚨 WARNING: IntaSend API keys missing. Payment features will fail.")
    else:
        print("💳 IntaSend Sandbox keys loaded.")

    # Debugging: Log the connection type to ensure we aren't using a local "ghost" SQLite file
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_mode = "PostgreSQL (Cloud)" if "postgresql" in db_uri else "SQLite (Local File)"
    
    # Security Hardening: Environment Validation
    if not app.debug:
        if app.secret_key == 'tum_market_secret':
            print("🚨 SECURITY WARNING: Using default SECRET_KEY in production!")
        if not os.environ.get('CLOUDINARY_URL') and not os.environ.get('CLOUDINARY_API_KEY'):
            print("🚨 configuration WARNING: Cloudinary credentials missing. Image uploads will fail.")
            
    # Debug: Check for specific critical environment variables in Debug mode
    if app.debug:
        print("🔍 Environment Check:")
        print(f"   - DATABASE_URL: {'✅ Set' if os.environ.get('DATABASE_URL') else '❌ MISSING'}")
        print(f"   - SECRET_KEY: {'✅ Custom' if app.secret_key != 'tum_market_secret' else '⚠️ DEFAULT'}")

    print(f"🚀 Database connected! Mode: {db_mode}")

@app.after_request
def disable_api_caching(response):
    # Force the browser to always fetch fresh data for API calls to prevent ghosting
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    return response

@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/profile')
def profile_page():
    return send_from_directory(STATIC_FOLDER, 'profile.html')

@app.route('/admin/verify')
@login_required
def admin_verify_page():
    return send_from_directory(STATIC_FOLDER, 'admin_verify.html')

@app.route('/services')
def services_page():
    return send_from_directory('services', 'index.html')

@app.route('/services/<path:filename>')
def serve_services_assets(filename):
    """Serves JS and CSS specifically for the independent services folder."""
    return send_from_directory('services', filename)

@app.route('/api/signup', methods=['POST'])
@limiter.limit("5 per hour") # Prevent account creation spam
def signup():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    phone_number = data.get('phone_number', '').strip()
    skills = data.get('skills', '').strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    # Kenyan mobile regex: supports 07..., 01..., +2547..., +2541..., 2547..., 2541...
    if phone_number and not re.match(r"^(?:0|\+?254)(?:1|7)\d{8}$", phone_number):
        return jsonify({"success": False, "message": "Invalid Kenyan phone number format."}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
        return jsonify({"success": False, "message": "Email is already registered."}), 400

    # Automatically grant admin privileges to the project creator
    is_admin_user = (email == 'osambojoshua5@gmail.com')

    new_user = User(
        name=name, 
        email=email, 
        password=generate_password_hash(password),
        phone_number=phone_number,
        skills=skills,
        is_admin=is_admin_user
    )
    db.session.add(new_user)
    db.session.commit()

    session['user_id'] = new_user.id
    session['user_name'] = name
    session['user_email'] = email

    return jsonify({
        "success": True,
        "message": "Account created successfully!",
        "name": name,
        "id": new_user.id,
        "email": email,
        "profile_picture": None,
        "is_admin": is_admin_user
    })

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute") # Brute force protection
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

    if user and check_password_hash(user.password, password):
        # Recognition logic: Ensure the creator is always an admin upon login
        if user.email == 'osambojoshua5@gmail.com' and not user.is_admin:
            user.is_admin = True
            db.session.commit()

        if user.is_suspended:
            return jsonify({"success": False, "message": "Your account has been suspended for violating marketplace rules."}), 403
            
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        return jsonify({
            "success": True,
            "message": "Welcome back!",
            "name": user.name,
            "id": user.id,
            "email": user.email,
            "profile_picture": user.profile_picture,
            "is_admin": user.is_admin
        })

    return jsonify({"success": False, "message": "Invalid email or password."}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route('/api/user/session', methods=['GET'])
def get_session():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        return jsonify({
            "logged_in": True,
            "id": session['user_id'],
            "name": session['user_name'],
            "email": session['user_email'],
            "profile_picture": user.profile_picture if user else None,
            "is_subscribed": user.is_subscribed if user else True,
            "subscription_updated_at": user.subscription_updated_at.isoformat() if user and user.subscription_updated_at else None,
            "is_skill_verified": user.is_skill_verified if user else False,
            "is_suspended": user.is_suspended if user else False,
            "is_admin": user.is_admin if user else False,
            "phone_number": user.phone_number if user else None,
            "skills": user.skills if user else None,
            "verified_skills": user.verified_skills if user else None,
            "verification_doc": user.resume_url if user else None
        })
    return jsonify({"logged_in": False})

@app.route('/api/user/subscription', methods=['POST'])
@login_required
def update_subscription_status():
    data = request.get_json() or {}
    status = data.get('is_subscribed')
    if status is None:
        return jsonify({"success": False, "message": "Missing status"}), 400
        
    user = db.session.get(User, session['user_id'])
    user.is_subscribed = bool(status)
    user.subscription_updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"success": True, "is_subscribed": user.is_subscribed, 
                    "subscription_updated_at": user.subscription_updated_at.isoformat()})

@app.route('/api/user/profile-picture', methods=['POST'])
@login_required
@not_suspended
def update_profile_picture():
    data = request.get_json() or {}
    image = data.get('image', '').strip()
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    try:
        secure_url = upload_image_to_cloudinary(image, folder="tum_market/profiles")
        if not secure_url:
             return jsonify({"success": False, "message": "Invalid image data."}), 400
        
        user.profile_picture = secure_url
        db.session.commit()
        return jsonify({"success": True, "message": "Profile picture updated!", "profile_picture": secure_url})
    except Exception as e:
        app.logger.error(f"Cloudinary Profile Upload Error: {str(e)}")
        return jsonify({"success": False, "message": f"Cloudinary error: {str(e)}"}), 500

@app.route('/api/user/profile', methods=['PATCH'])
@login_required
@not_suspended
def update_user_profile():
    data = request.get_json() or {}
    user = db.session.get(User, session['user_id'])
    
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    name = data.get('name', '').strip()
    phone = data.get('phone_number', '').strip()
    skills = data.get('skills', '').strip()

    if name:
        user.name = name
        session['user_name'] = name # Sync session name
    
    if phone:
        # Kenyan mobile regex: supports 07..., 01..., +2547..., +2541..., 2547..., 2541...
        if not re.match(r"^(?:0|\+?254)(?:1|7)\d{8}$", phone):
            return jsonify({"success": False, "message": "Invalid Kenyan phone number format."}), 400
        user.phone_number = phone

    if 'skills' in data:
        user.skills = skills

    db.session.commit()
    return jsonify({"success": True, "message": "Profile updated successfully!"})

@app.route('/api/listings', methods=['GET'])
def get_listings():
    try:
        stmt = db.select(Listing).filter_by(status='available')
        listings = db.session.execute(stmt).scalars().all()
        
        # Efficient serialization using list comprehension
        available_listings = [{
            "id": l.id,
            "title": l.title or "Untitled Item",
            "price": float(l.price) if l.price else 0.0,
            "location": l.location or "Unknown Location",
            "category": l.category or "General",
            "image": l.image or "", 
            "seller_phone": l.seller_phone or "N/A",
            "posted_by": l.posted_by or "Anonymous",
            "status": l.status or "available",
            "tier": l.tier or "free",
            "views": int(l.views or 0)
        } for l in listings]
            
        return jsonify({"success": True, "listings": available_listings})

    except Exception:
        print("❌ CRITICAL ERROR in /api/listings:")
        traceback.print_exc()
        return jsonify({"status": "error", "listings": [], "success": False}), 200

@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        stmt = db.select(Listing.category).filter_by(status='available').distinct()
        categories = db.session.execute(stmt).scalars().all()
        return jsonify({"success": True, "categories": [c for c in categories if c]})
    except Exception:
        print("❌ CRITICAL ERROR in /api/listings:")
        traceback.print_exc()
        return jsonify({"status": "error", "listings": [], "success": False}), 200

@app.route('/api/listings', methods=['POST'])
@login_required
@not_suspended
def create_listing():
    data = request.get_json() or {}
    
    title = data.get('title', '').strip()
    location = data.get('location', '').strip()
    category = data.get('category', '').strip()
    seller_phone = data.get('seller_phone', '').strip()
    image = data.get('image', '').strip()
    tier = data.get('tier', 'free')

    try:
        price = float(data.get('price', 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid price format."}), 400

    if not all([title, location, category, seller_phone]):
        return jsonify({"success": False, "message": "All fields (Title, Price, Location, Category, Phone) are required."}), 400
    
    # Kenyan mobile regex: supports 07..., 01..., +2547..., +2541..., 2547..., 2541...
    if price <= 0:
        return jsonify({"success": False, "message": "Price must be a positive number."}), 400

    if not re.match(r"^\+?1?\d{9,15}$", seller_phone):
        return jsonify({"success": False, "message": "Invalid phone number format."}), 400

    try:
        image_url = upload_image_to_cloudinary(image, folder="tum_market/listings")
    except Exception as e:
        return jsonify({"success": False, "message": f"Image upload error: {str(e)}"}), 500

    new_item = Listing(
        title=title,
        price=price,
        location=location,
        category=category,
        image=image_url,
        seller_phone=seller_phone,
        posted_by=session['user_name'],
        user_id=session['user_id'],
        tier=tier
    )

    db.session.add(new_item)
    db.session.commit()
    return jsonify({"success": True, "message": "Listing posted successfully!"})

@app.route('/api/listings/<int:listing_id>', methods=['PUT', 'DELETE'])
@login_required
@not_suspended
def handle_single_listing(listing_id):
    target = db.session.get(Listing, listing_id)
    if not target:
        return jsonify({"success": False, "message": "Listing not found."}), 404
    
    if target.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    if request.method == 'DELETE':
        db.session.delete(target)
        db.session.commit()
        return jsonify({"success": True, "message": "Listing deleted successfully."})

    if request.method == 'PUT':
        data = request.get_json() or {}
        if 'title' in data: target.title = data['title'].strip()
        if 'location' in data: target.location = data['location'].strip()
        if 'category' in data: target.category = data['category'].strip()
        if 'seller_phone' in data: target.seller_phone = data['seller_phone'].strip()
        if 'price' in data:
            try:
                target.price = float(data['price'])
            except (ValueError, TypeError):
                pass

        try:
            new_image_url = upload_image_to_cloudinary(data.get('image', ''), folder="tum_market/listings")
            if new_image_url:
                target.image = new_image_url
        except Exception as e:
            return jsonify({"success": False, "message": f"Image update error: {str(e)}"}), 500

        db.session.commit()
        return jsonify({"success": True, "message": "Listing updated successfully!"})

@app.route('/api/listings/<int:listing_id>/view', methods=['POST'])
def increment_listing_view(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        return jsonify({"success": False, "message": "Listing not found"}), 404
    
    # Log the specific view event with a timestamp for the weekly report
    new_view = ListingView(listing_id=listing_id)
    db.session.add(new_view)
    
    listing.views = (listing.views or 0) + 1
    db.session.commit()
    return jsonify({"success": True, "views": listing.views})

@app.route('/api/admin/generate-weekly-reports', methods=['POST'])
def generate_weekly_reports():
    """Triggered via Cron Job to send sellers their 7-day view stats."""
    auth_key = request.headers.get('X-Admin-Key')
    if not auth_key or auth_key != os.environ.get('ADMIN_RESET_KEY'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    users = db.session.execute(db.select(User).filter_by(is_subscribed=True)).scalars().all()
    s = URLSafeTimedSerializer(app.secret_key)
    
    for user in users:
        # Aggregate views for all listings belonging to this user in the last 7 days
        stmt = db.select(db.func.count(ListingView.id)).join(Listing).filter(
            Listing.user_id == user.id,
            ListingView.created_at >= seven_days_ago
        )
        new_views_count = db.session.execute(stmt).scalar() or 0
        
        if new_views_count > 0:
            new_noti = Notification(
                user_id=user.id,
                type='weekly_summary',
                title='📈 Weekly View Summary',
                message=f"Your listings received {new_views_count} new views in the last 7 days. Keep up the great work!"
            )
            db.session.add(new_noti)
            
            # Send Email Notification
            token = s.dumps(user.id, salt='unsubscribe-salt')
            unsubscribe_url = f"https://tum-market.onrender.com/api/unsubscribe?token={token}"
            
            text_body = (
                f"Hi {user.name},\n\n"
                f"Your listings on TUM Market received {new_views_count} new views in the last 7 days. "
                f"Keep up the great work!\n\nBest,\nThe TUM Market Team\n\n"
                f"To unsubscribe from these reports, visit: {unsubscribe_url}"
            )

            html_body = f"""
            <html>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 0;">
                <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; margin-top: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                    <tr>
                        <td bgcolor="#020617" style="padding: 40px 0 30px 0; text-align: center;">
                            <h1 style="color: #ef4444; margin: 0; letter-spacing: 2px;">TUM MARKET</h1>
                            <p style="color: #ffffff; font-size: 14px; margin-top: 5px;">Weekly Performance Report</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px 40px 30px;">
                            <h2 style="color: #0f172a; margin-top: 0;">Hello, {user.name}!</h2>
                            <p style="color: #475569; font-size: 16px; line-height: 1.6;">
                                We've been tracking your listings over the past week, and we have some exciting news! Your shop is gaining momentum.
                            </p>
                            <div style="background-color: #f8fafc; border-left: 4px solid #ef4444; padding: 20px; margin: 25px 0; text-align: center;">
                                <span style="display: block; font-size: 14px; color: #64748b; text-transform: uppercase; font-weight: bold;">New Views (Last 7 Days)</span>
                                <span style="display: block; font-size: 48px; color: #0f172a; font-weight: 800;">{new_views_count}</span>
                            </div>
                            <p style="color: #475569; font-size: 16px; line-height: 1.6;">
                                Keep your items fresh and high-quality to attract even more potential buyers.
                            </p>
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 30px;">
                                <tr>
                                    <td align="center">
                                        <a href="https://tum-market.onrender.com/profile" style="background-color: #2563eb; color: #ffffff; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Manage My Listings</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td bgcolor="#f1f5f9" style="padding: 20px 30px; text-align: center; color: #94a3b8; font-size: 12px;">
                            &copy; 2024 TUM Market. All rights reserved.<br>
                            You are receiving this because you have an active seller account on TUM Market.<br>
                            <a href="{unsubscribe_url}" style="color: #94a3b8; text-decoration: underline;">Unsubscribe from these reports</a>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
            send_email(user.email, "📈 Your Weekly TUM Market Summary", text_body, html_body)
            
    db.session.commit()
    return jsonify({"success": True, "message": f"Weekly reports generated for {len(users)} users."})

@app.route('/api/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    """Allows users to opt-out of weekly email reports."""
    token = request.args.get('token')
    if not token:
        return "Missing token.", 400
    

    s = URLSafeTimedSerializer(app.secret_key)
    try:
        # Token valid for 30 days (2592000 seconds)
        user_id = s.loads(token, salt='unsubscribe-salt', max_age=2592000)
    except:
        return "<h1>Invalid or Expired Link</h1><p>This unsubscribe link is no longer valid.</p>", 400
        
    user = db.session.get(User, user_id)
    if not user:
        return "User not found.", 404

    if request.method == 'POST':
        user.is_subscribed = False
        db.session.commit()
        return "<h1>Unsubscribed</h1><p>You have been successfully unsubscribed from TUM Market weekly reports.</p>", 200

    # Display confirmation page for GET requests
    return f"""
    <html>
    <head>
        <title>Unsubscribe - TUM Market</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #020617; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: #0f172a; padding: 40px; border-radius: 12px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 400px; border: 1px solid rgba(255,255,255,0.1); }}
            h1 {{ color: #ef4444; margin-top: 0; }}
            p {{ color: #94a3b8; margin-bottom: 30px; line-height: 1.6; }}
            button {{ background: #ef4444; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; font-size: 1rem; }}
            button:hover {{ background: #dc2626; transform: translateY(-2px); }}
            a {{ color: #94a3b8; text-decoration: none; display: block; margin-top: 20px; font-size: 0.9rem; }}
            a:hover {{ color: white; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Unsubscribe</h1>
            <p>Hello <strong>{user.name}</strong>, are you sure you want to stop receiving weekly performance reports for your listings on TUM Market?</p>
            <form method="POST">
                <button type="submit">Confirm Unsubscribe</button>
            </form>
            <a href="/">Return to Marketplace</a>
        </div>
    </body>
    </html>
    """, 200

@app.route('/api/user/listings', methods=['GET'])
def get_user_listings():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    listings = db.session.execute(db.select(Listing).filter_by(user_id=session['user_id'])).scalars().all()
    jobs = db.session.execute(db.select(JobPosting).filter_by(user_id=session['user_id'])).scalars().all()
    total_views = sum(l.views or 0 for l in listings)
    
    user_items = [{
        "id": l.id, "title": l.title, "price": l.price, "location": l.location,
        "category": l.category, "seller_phone": l.seller_phone, "image": l.image,
        "status": l.status, "tier": l.tier, "views": l.views} for l in listings]

    user_jobs = [{
        "id": j.id, "title": j.title, "budget": j.budget, "status": j.status,
        "created_at": j.created_at.isoformat()} for j in jobs]

    return jsonify({"success": True, "listings": user_items, "jobs": user_jobs, "total_views": total_views})

@app.route('/api/user/listings/clear', methods=['DELETE'])
def clear_user_listings():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    # Efficiently delete all listings belonging to the session user
    db.session.query(Listing).filter_by(user_id=session['user_id']).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"success": True, "message": "All your listings have been removed."})

@app.route('/api/listings/<int:listing_id>/sold', methods=['POST', 'PATCH'])
def mark_as_sold_api(listing_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    listing = db.session.get(Listing, listing_id)
    if not listing:
        return jsonify({"success": False, "message": "Item not found."}), 404
    
    if listing.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    listing.status = 'sold'
    db.session.commit()
    return jsonify({"success": True, "message": "Item successfully marked as sold!"})

@app.route('/api/notifications')
def get_notifications():
    user_id = session.get('user_id')
    # Show notifications that are either global (user_id is null) OR for this user
    # and are not yet marked as read.
    stmt = db.select(Notification).filter(
        (Notification.user_id == None) | (Notification.user_id == user_id),
        Notification.is_read == False
    ).order_by(Notification.created_at.desc())
    
    notifications = db.session.execute(stmt).scalars().all()
    return jsonify([
        {"id": n.id, "title": n.title, "message": n.message, "time": n.created_at.strftime('%Y-%m-%d %H:%M'), "type": n.type} 
        for n in notifications
    ])

@app.route('/api/notifications/<int:noti_id>/read', methods=['POST'])
def mark_notification_read(noti_id):
    notification = db.session.get(Notification, noti_id)
    if not notification:
        return jsonify({"success": False, "message": "Notification not found"}), 404
    
    notification.is_read = True
    db.session.commit()
    return jsonify({"success": True})

@app.route('/api/notifications/<int:noti_id>', methods=['DELETE'])
def delete_single_notification(noti_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    notification = db.session.get(Notification, noti_id)
    if not notification:
        return jsonify({"success": False, "message": "Notification not found"}), 404
    
    if notification.user_id and notification.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403
    
    db.session.delete(notification)
    db.session.commit()
    return jsonify({"success": True, "message": "Notification deleted."})

@app.route('/api/notifications/clear', methods=['DELETE'])
def clear_notifications():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user_id = session['user_id']
    # Hard delete notifications to truly clear the database of old entries
    db.session.query(Notification).filter(
        (Notification.user_id == None) | (Notification.user_id == user_id)
    ).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"success": True, "message": "All notifications cleared."})

# --- Matchmaking & Notification Pipeline ---

def dispatch_alerts(matches: List[TakerMatch], job_title: str):
    """Iterates through verified matches and triggers broadcast pipelines."""
    for match in matches:
        # 1. SMTP Email Dispatcher Boilerplate
        subject = f"🎯 New Job Match: {job_title}"
        text_body = f"Hello! A new project brief matching your verified skills has been posted: {job_title}. Check your dashboard to apply!"
        # send_email(match.email, subject, text_body)
        app.logger.info(f"📧 Email pipeline queued for: {match.email}")

        # 2. SMS Delivery Boilerplate (e.g., Africa's Talking Gateway)
        sms_message = f"TUM Market: New match found! '{job_title}' aligns with your verified skills. Apply now."
        # AT_USERNAME = os.environ.get('AT_USERNAME')
        # AT_API_KEY = os.environ.get('AT_API_KEY')
        # Integration code for Africa's Talking goes here
        app.logger.info(f"📱 SMS pipeline triggered for: {match.phone_number}")

def run_matchmaking_pipeline(job):
    """Queries verified talent, evaluates semantics via Gemini, and returns structured matches."""
    # 1. Query the Talent Pool (Verified Takers)
    if not client:
        app.logger.error("Matchmaking skipped: Gemini Client not initialized.")
        return []

    verified_users = db.session.execute(
        db.select(User).filter_by(is_skill_verified=True, is_suspended=False)
    ).scalars().all()

    if not verified_users:
        return []

    talent_pool = [
        {
            "talent_id": u.id,
            "phone_number": u.phone_number or "N/A",
            "email": u.email,
            "skills_list": (u.skills or "").split(",")
        } for u in verified_users
    ]

    # 2. Construct the Cognitive Prompt
    prompt = f"""
    Job Title: {job.title}
    Job Description: {job.description}
    Required Skills (Tags): {job.skills}

    Talent Pool:
    {json.dumps(talent_pool, indent=2)}
    """

    try:
        # 3. Gemini Semantic Matching
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                system_instruction="You are the TUM Market Matching Algorithm. Perform a semantic skill evaluation. Match students whose verified background aligns with the project scope. Only return strong matches.",
                response_mime_type="application/json",
                response_schema=MatchmakerPayload,
            )
        )
        
        if response.parsed:
            return response.parsed.matches
        return []
    except Exception as e:
        app.logger.error(f"Gemini Matchmaking Error: {str(e)}")
        return []

# --- Verification PDF Helper ---
def upload_pdf_to_cloudinary(pdf_data):
    """Helper to handle base64 PDF or Image uploads to Cloudinary for verification."""
    if not pdf_data or not (pdf_data.startswith('data:application/pdf;') or pdf_data.startswith('data:image/')):
        return None
    try:
        # PDFs can be larger, setting a 10MB limit
        if len(pdf_data) > 14_000_000: # Base64 overhead
            raise ValueError("PDF is too large (max 10MB).")
            
        upload_result = cloudinary.uploader.upload(
            pdf_data, 
            folder="tum_market/resumes",
            resource_type="auto" # Important for non-image files
        )
        return upload_result.get('secure_url')
    except Exception as e:
        app.logger.error(f"Cloudinary PDF Upload Error: {str(e)}")
        raise e

@app.route('/api/user/request-verification', methods=['POST'])
@login_required
@not_suspended
def request_verification():
    data = request.get_json() or {}
    resume_data = data.get('doc', '').strip()
    
    user = db.session.get(User, session['user_id'])
    url = upload_pdf_to_cloudinary(resume_data)
    if not url:
        return jsonify({"success": False, "message": "Invalid PDF data."}), 400
        
    user.resume_url = url
    user.verification_status = 'pending'
    db.session.commit()
    return jsonify({"success": True, "message": "Verification request submitted!"})

@app.route('/api/jobs/<int:job_id>/appeal', methods=['POST'])
@login_required
@not_suspended
def appeal_job_suspension(job_id):
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({"success": False, "message": "Appeal reason is required."}), 400
    
    job = db.session.get(JobPosting, job_id)
    if not job or job.user_id != session['user_id']:
        return jsonify({"success": False, "message": "Job not found or access denied."}), 404
    
    if job.status != 'suspended':
        return jsonify({"success": False, "message": "This job is not suspended."}), 400

    # Check for existing pending appeal
    existing = db.session.execute(db.select(Appeal).filter_by(job_id=job_id, status='pending')).scalar_one_or_none()
    if existing:
        return jsonify({"success": False, "message": "An appeal is already pending for this job."}), 409

    new_appeal = Appeal(job_id=job_id, user_id=session['user_id'], reason=reason)
    db.session.add(new_appeal)
    db.session.commit()
    return jsonify({"success": True, "message": "Appeal submitted successfully."})

@app.route('/api/submit-job', methods=['POST'])
@login_required
@not_suspended
def submit_job_posting():
    data = request.get_json() or {}
    
    client_name = data.get('client_name', '').strip()
    client_contact = data.get('client_contact', '').strip()
    job_title = data.get('job_title', '').strip()
    job_description = data.get('job_description', '').strip()
    required_skill = data.get('required_skill', '').strip() # This will be a single skill from dropdown
    budget_amount = data.get('budget_amount')
    budget_type = data.get('budget_type', '').strip()

    if not all([client_name, client_contact, job_title, job_description, required_skill, budget_amount, budget_type]):
        return jsonify({"success": False, "message": "All fields are required."}), 400
    
    # --- Daily Job Posting Rate Limit ---
    # Check how many jobs the user has posted in the last 24 hours
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_jobs_count = db.session.execute(
        db.select(db.func.count(JobPosting.id)).filter(
            JobPosting.user_id == session['user_id'],
            JobPosting.created_at >= twenty_four_hours_ago
        )
    ).scalar()

    # Basic validation for contact (can be email or phone)
    # Kenyan mobile regex: supports 07..., 01..., +2547..., +2541..., 2547..., 2541...
    if '@' in client_contact and not re.match(r"[^@]+@[^@]+\.[^@]+", client_contact):
        return jsonify({"success": False, "message": "Invalid email format for client contact."}), 400
    elif not re.match(r"^(?:0|\+?254)(?:1|7)\d{8}$", client_contact):
        return jsonify({"success": False, "message": "Invalid phone number format for client contact."}), 400

    if recent_jobs_count >= 3:
        return jsonify({"success": False, "message": "Daily job posting limit reached (3 jobs). Verify account to unlock premium tiers."}), 429

    # Format budget string
    budget_str = f"KES {budget_amount} ({budget_type})"

    user = db.session.get(User, session['user_id'])
    is_poster_verified = user.is_skill_verified if user else False

    new_job = JobPosting(
        title=job_title,
        description=job_description,
        client_name=client_name,
        client_contact=client_contact,
        budget=budget_str,
        skills=required_skill, # Storing as a single skill for now, can be extended to comma-separated
        posted_by=session['user_name'],
        user_id=session['user_id'],
        verified_client=is_poster_verified
    )
    db.session.add(new_job)
    db.session.commit()

    # Trigger Automated Matchmaking and Notification Pipeline
    try:
        matches = run_matchmaking_pipeline(new_job)
        dispatch_alerts(matches, new_job.title)
    except Exception as e:
        app.logger.error(f"Matchmaking Pipeline Failure: {str(e)}")

    return jsonify({"success": True, "message": "Project brief submitted successfully!"})

# --- Service Portal API ---

@app.route('/api/jobs', methods=['GET'])
def get_job_postings():
    stmt = db.select(JobPosting).order_by(JobPosting.created_at.desc())
    jobs = db.session.execute(stmt).scalars().all()
    
    user_applications = []
    if 'user_id' in session:
        user_applications = db.session.execute(
            db.select(JobApplication.job_id).filter_by(talent_id=session['user_id'])
        ).scalars().all()

    return jsonify({
        "success": True,
        "jobs": [{
            "id": j.id,
            "title": j.title,
            "description": j.description,
            "budget": j.budget,
            "skills": j.skills.split(',') if j.skills else [],
            "poster": j.posted_by,
            "verified": j.verified_client,
            "created_at": j.created_at.isoformat(),
            "has_applied": j.id in user_applications
        } for j in jobs]
    })

@app.route('/api/apply-job/<int:job_id>', methods=['POST'])
@login_required
@not_suspended
def apply_to_job(job_id):
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_skill_verified:
        return jsonify({"success": False, "message": "Only verified student takers can apply."}), 403

    job = db.session.get(JobPosting, job_id)
    if not job:
        return jsonify({"success": False, "message": "Project brief not found."}), 404

    # Check for existing application to prevent duplicates
    existing = db.session.execute(
        db.select(JobApplication).filter_by(job_id=job_id, talent_id=user.id)
    ).scalar_one_or_none()
    
    if existing:
        return jsonify({"success": False, "message": "You have already applied for this project."}), 409

    new_application = JobApplication(job_id=job_id, talent_id=user.id)
    db.session.add(new_application)
    
    # Client Alert Boilerplate: Notify the job poster
    client = db.session.get(User, job.user_id)
    if client:
        subject = "🚀 New Professional Applicant: " + job.title
        text = f"Hello {client.name}, a verified student ({user.name}) has applied for your brief. Check your portal to review their profile."
        send_email(client.email, subject, text)

    db.session.commit()
    return jsonify({"success": True, "message": "Application submitted successfully! The client has been notified."})

@app.route('/api/jobs', methods=['POST'])
@login_required
@not_suspended
def create_job_posting():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    
    if not title or not description:
        return jsonify({"success": False, "message": "Title and Description are required."}), 400

    new_job = JobPosting(
        title=title,
        description=description,
        budget=data.get('budget', 'Negotiable'),
        skills=",".join(data.get('skills', [])),
        posted_by=session['user_name'],
        user_id=session['user_id'],
        verified_client=True # Defaulting to True for registered users in this phase
    )
    db.session.add(new_job)
    db.session.commit()
    return jsonify({"success": True, "message": "Project brief broadcasted!"})

# --- Admin Verification API ---

@app.route('/api/admin/unverified-takers', methods=['GET'])
@admin_required
def get_unverified_takers():
    stmt = db.select(User).filter_by(verification_status='pending', is_admin=False)
    users = db.session.execute(stmt).scalars().all()
    return jsonify({
        "success": True,
        "users": [{"id": u.id, "name": u.name, "email": u.email, "doc": u.resume_url, "skills": u.skills} for u in users]
    })

@app.route('/api/admin/verify-taker/<int:user_id>', methods=['POST'])
@admin_required
def verify_taker(user_id):
    data = request.get_json() or {}
    verified_skills = data.get('verified_skills', [])

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    
    user.is_skill_verified = True
    user.verification_status = 'verified'
    user.verified_skills = ",".join(verified_skills) if verified_skills else ""
    
    # Create an In-App Notification
    new_noti = Notification(
        user_id=user.id,
        type='verification_success',
        title='✅ Skill Verification Approved!',
        message='Congratulations! Your taker profile has been verified. You can now apply for professional jobs.'
    )
    db.session.add(new_noti)
    db.session.commit()

    # Prepare Email Content
    subject = "🎉 Verification Approved - TUM Market"
    text_body = f"Hi {user.name},\n\nGreat news! Your verification request has been approved. You are now a Verified Taker on TUM Market.\n\nYou can now browse the Service Portal and apply for professional project briefs.\n\nBest,\nThe TUM Market Team"
    
    html_body = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 0;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; margin-top: 40px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            <tr>
                <td bgcolor="#0f172a" style="padding: 40px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; letter-spacing: 1px;">TUM MARKET</h1>
                    <p style="color: #94a3b8; font-size: 14px; margin-top: 5px;">Professional Verification</p>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px;">
                    <h2 style="color: #1e293b; margin-top: 0;">Congratulations, {user.name}!</h2>
                    <p style="color: #475569; font-size: 16px; line-height: 1.6;">
                        Your verification request has been reviewed and <strong>approved</strong> by our admin team.
                    </p>
                    <div style="background-color: #f1f5f9; border-left: 4px solid #10b981; padding: 20px; margin: 25px 0;">
                        <p style="margin: 0; color: #0f172a; font-weight: 600;">You are now a Verified Taker!</p>
                        <p style="margin: 5px 0 0 0; color: #64748b; font-size: 14px;">You can now apply for project briefs and offer professional services on the platform.</p>
                    </div>
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 30px;">
                        <tr>
                            <td align="center">
                                <a href="https://tum-market.onrender.com/services" style="background-color: #2563eb; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Browse Service Portal</a>
                            </td>
                        </tr>
                    </table>
                    <p style="color: #94a3b8; font-size: 14px; margin-top: 30px; text-align: center;">
                        If you have any questions, please contact our support team.
                    </p>
                </td>
            </tr>
            <tr>
                <td bgcolor="#f8fafc" style="padding: 20px; text-align: center; color: #94a3b8; font-size: 12px;">
                    &copy; 2024 TUM Market. All rights reserved.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Trigger Email
    send_email(user.email, subject, text_body, html_body)

    return jsonify({"success": True, "message": f"User {user.name} is now a Verified Taker."})

@app.route('/api/admin/reject-taker/<int:user_id>', methods=['POST'])
@admin_required
def reject_taker(user_id):
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    
    if not reason:
        return jsonify({"success": False, "message": "Please provide a reason for rejection."}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
    
    # Reset status so the user can address feedback and re-upload
    user.verification_status = 'none'
    user.resume_url = None
    
    # Create an In-App Notification
    new_noti = Notification(
        user_id=user.id,
        type='verification_rejected',
        title='❌ Verification Request Declined',
        message=f'Your taker verification was declined. Reason: {reason}'
    )
    db.session.add(new_noti)
    db.session.commit()

    # Prepare Email Content
    subject = "Update: Verification Request Declined - TUM Market"
    text_body = f"Hi {user.name},\n\nYour verification request has been declined for the following reason:\n{reason}\n\nYou can re-submit your profile for verification after addressing the feedback."
    
    html_body = f"""
    <html>
    <body style="font-family: 'Segoe UI', sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
            <div style="background: #ef4444; padding: 30px; text-align: center; color: white;">
                <h1 style="margin: 0;">TUM MARKET</h1>
            </div>
            <div style="padding: 30px;">
                <h2 style="color: #1e293b;">Hello, {user.name}</h2>
                <p style="color: #475569;">Your verification request has been declined. Our admin team provided the following feedback:</p>
                <div style="background: #fff1f2; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0; color: #991b1b;">
                    <strong>Feedback:</strong> {reason}
                </div>
                <p style="color: #475569;">You can update your profile and re-submit your resume in your dashboard.</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email(user.email, subject, text_body, html_body)

    return jsonify({"success": True, "message": "Rejection processed and email sent."})

@app.route('/api/jobs/<int:job_id>/report', methods=['POST'])
@login_required
@not_suspended
def report_job_posting(job_id):
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()

    if not reason:
        return jsonify({"success": False, "message": "A reason for reporting is required."}), 400

    job = db.session.get(JobPosting, job_id)
    if not job:
        return jsonify({"success": False, "message": "Job posting not found."}), 404
    
    # Prevent self-reporting
    if job.user_id == session['user_id']:
        return jsonify({"success": False, "message": "You cannot report your own job posting."}), 403

    # Check if user has already reported this job
    existing_report = db.session.execute(db.select(Report).filter_by(job_id=job_id, reporter_id=session['user_id'], status='pending')).scalar_one_or_none()
    if existing_report:
        return jsonify({"success": False, "message": "You have already reported this job posting."}), 409

    new_report = Report(
        job_id=job_id,
        reporter_id=session['user_id'],
        reason=reason
    )
    db.session.add(new_report)

    # Notify admins about the new report
    admin_noti = Notification(
        user_id=None, # Global notification for all admins
        type='new_report',
        title='🚨 New Job Report',
        message=f'Job "{job.title}" (ID: {job.id}) has been reported by {session["user_name"]}.'
    )
    db.session.add(admin_noti)

    db.session.commit()
    return jsonify({"success": True, "message": "Job posting reported successfully. Our team will review it."})

# --- Admin Reports API ---

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    users = db.session.execute(db.select(User)).scalars().all()
    return jsonify({
        "success": True,
        "users": [{"id": u.id, "name": u.name, "email": u.email, "is_suspended": u.is_suspended, "is_admin": u.is_admin} for u in users]
    })

@app.route('/api/admin/toggle-suspension/<int:user_id>', methods=['POST'])
@admin_required
def toggle_suspension(user_id):
    if user_id == session['user_id']:
        return jsonify({"success": False, "message": "You cannot suspend yourself."}), 400
        
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404
        
    user.is_suspended = not user.is_suspended

    # Automatically handle listings visibility
    if user.is_suspended:
        # Hide available listings by marking them as 'suspended'
        db.session.execute(
            db.update(Listing)
            .filter_by(user_id=user.id, status='available')
            .values(status='suspended')
        )
    else:
        # Restore suspended listings back to 'available'
        db.session.execute(
            db.update(Listing)
            .filter_by(user_id=user.id, status='suspended')
            .values(status='available')
        )

    db.session.commit()
    
    action = "suspended" if user.is_suspended else "unsuspended"
    subject = "Account Update - TUM Market"
    text_body = f"Hello {user.name}, your account on TUM Market has been {action} for violating marketplace rules."
    send_email(user.email, subject, text_body)
    
    return jsonify({"success": True, "message": f"User {user.name} has been {action}."})

@app.route('/api/admin/reports', methods=['GET'])
@admin_required
def get_pending_reports():
    stmt = db.select(Report).filter_by(status='pending').order_by(Report.created_at.desc())
    reports = db.session.execute(stmt).scalars().all()
    return jsonify({
        "success": True,
        "reports": [{
            "id": r.id,
            "job_id": r.job_id,
            "reason": r.reason,
            "created_at": r.created_at.isoformat()
        } for r in reports]
    })

@app.route('/api/admin/reports/<int:report_id>/action', methods=['POST'])
@admin_required
def take_report_action(report_id):
    data = request.get_json() or {}
    action = data.get('action') # 'dismiss' or 'suspend'
    reason = data.get('reason', '').strip()
    
    report = db.session.get(Report, report_id)
    if not report:
        return jsonify({"success": False, "message": "Report not found."}), 404

    if action == 'dismiss':
        report.status = 'dismissed'
        msg = "Report dismissed."
    elif action == 'suspend':
        if not reason:
            return jsonify({"success": False, "message": "Reason is required for suspension."}), 400

        job = db.session.get(JobPosting, report.job_id)
        if job:
            job.status = 'suspended'
            
            # Notify the job poster
            poster = db.session.get(User, job.user_id)
            if poster:
                # Create In-App Notification
                new_noti = Notification(
                    user_id=poster.id,
                    type='job_suspended',
                    title='⚠️ Job Posting Suspended',
                    message=f'Your job posting "{job.title}" has been suspended. Reason: {reason}'
                )
                db.session.add(new_noti)

                # Send Email Notification
                subject = "⚠️ Important: Your Job Posting has been Suspended"
                text_body = f"Hello {poster.name},\n\nYour job posting '{job.title}' has been suspended by our moderation team for the following reason:\n\n{reason}\n\nIf you believe this is an error, please contact support."
                
                html_body = f"""
                <html>
                <body style="font-family: 'Segoe UI', sans-serif; background-color: #f8fafc; padding: 20px;">
                    <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                        <div style="background: #0f172a; padding: 30px; text-align: center; color: white;">
                            <h1 style="margin: 0;">TUM MARKET</h1>
                        </div>
                        <div style="padding: 30px;">
                            <h2 style="color: #1e293b;">Job Posting Update</h2>
                            <p style="color: #475569;">Hello {poster.name},</p>
                            <p style="color: #475569;">Your job posting <strong>"{job.title}"</strong> has been suspended because it was found to be in violation of our professional service guidelines.</p>
                            <div style="background: #fff1f2; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0; color: #991b1b;">
                                <strong>Reason for Suspension:</strong> {reason}
                            </div>
                            <p style="color: #475569;">If you believe this was an error, please reach out to our admin team for clarification.</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                send_email(poster.email, subject, text_body, html_body)

        # Once a job is suspended, the report is considered resolved/reviewed
        report.status = 'reviewed'
        msg = "Job suspended and report resolved."
    else:
        return jsonify({"success": False, "message": "Invalid action."}), 400

    db.session.commit()
    return jsonify({"success": True, "message": msg})

@app.route('/api/admin/appeals', methods=['GET'])
@admin_required
def get_pending_appeals():
    stmt = db.select(Appeal).filter_by(status='pending').order_by(Appeal.created_at.desc())
    appeals = db.session.execute(stmt).scalars().all()
    return jsonify({
        "success": True,
        "appeals": [{
            "id": a.id,
            "job_id": a.job_id,
            "user_id": a.user_id,
            "reason": a.reason,
            "created_at": a.created_at.isoformat()
        } for a in appeals]
    })

@app.route('/api/admin/appeals/<int:appeal_id>/action', methods=['POST'])
@admin_required
def take_appeal_action(appeal_id):
    data = request.get_json() or {}
    action = data.get('action') # 'approve' or 'reject'
    
    appeal = db.session.get(Appeal, appeal_id)
    if not appeal:
        return jsonify({"success": False, "message": "Appeal not found."}), 404
    
    job = db.session.get(JobPosting, appeal.job_id)
    user = db.session.get(User, appeal.user_id)

    if action == 'approve':
        appeal.status = 'approved'
        if job:
            job.status = 'active'
        msg = "Appeal approved. Job reinstated."
        if user:
            send_email(user.email, "Update: Job Appeal Approved", f"Your appeal for '{job.title if job else 'your job'}' was approved. The job is now active.")
    elif action == 'reject':
        appeal.status = 'rejected'
        msg = "Appeal rejected."
        if user:
            send_email(user.email, "Update: Job Appeal Rejected", f"Your appeal for '{job.title if job else 'your job'}' was rejected.")
    else:
        return jsonify({"success": False, "message": "Invalid action."}), 400
    
    db.session.commit()
    return jsonify({"success": True, "message": msg})

@app.route('/api/admin/jobs', methods=['GET'])
@admin_required
def get_all_jobs_admin():
    stmt = db.select(JobPosting).order_by(JobPosting.created_at.desc())
    jobs = db.session.execute(stmt).scalars().all()
    return jsonify({
        "success": True,
        "jobs": [{
            "id": j.id,
            "title": j.title,
            "poster": j.posted_by,
            "status": j.status,
            "created_at": j.created_at.isoformat()
        } for j in jobs]
    })

@app.route('/api/admin/jobs/<int:job_id>/applications', methods=['GET'])
@admin_required
def get_job_applications_admin(job_id):
    job = db.session.get(JobPosting, job_id)
    if not job:
        return jsonify({"success": False, "message": "Job not found."}), 404
        
    stmt = db.select(JobApplication, User).join(User, JobApplication.talent_id == User.id).filter(JobApplication.job_id == job_id)
    results = db.session.execute(stmt).all()
    
    applications = []
    for app_row, user in results:
        applications.append({
            "id": app_row.id,
            "applied_at": app_row.applied_at.isoformat(),
            "status": app_row.status,
            "talent": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone_number,
                "verified_skills": user.verified_skills.split(',') if user.verified_skills else [],
                "resume": user.resume_url
            }
        })
        
    return jsonify({
        "success": True,
        "job_title": job.title,
        "applications": applications
    })

@app.route('/<path:filename>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def serve_static(filename):
    if filename.startswith('api/'):
        return jsonify({"success": False, "message": "Invalid API endpoint."}), 404
    if request.method != 'GET':
        return jsonify({"success": False, "message": "Method not allowed for static files."}), 405

    return send_from_directory(STATIC_FOLDER, filename)

@app.cli.command("make-admin")
@click.argument("email")
def make_admin(email):
    """Promotes a user to admin status via CLI."""
    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if not user:
        print(f"❌ User with email {email} not found.")
        return
    
    user.is_admin = True
    db.session.commit()
    print(f"✅ User {user.name} ({email}) is now an Admin.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
