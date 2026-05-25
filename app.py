from flask import Flask, request, jsonify, send_from_directory, session
import smtplib
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_sqlalchemy import SQLAlchemy
import os
import re
import json
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import cloudinary
import cloudinary.uploader
from functools import wraps
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.url_map.strict_slashes = False  # Best practice: Treat /api/route and /api/route/ the same
app.secret_key = os.environ.get('SECRET_KEY', 'tum_market_secret')

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

def upload_image_to_cloudinary(image_data, folder="tum_market/general"):
    """Helper to handle base64 image uploads to Cloudinary."""
    if not image_data or not image_data.startswith('data:image/'):
        return None
        
    try:
        # Check size if needed (approx 5MB check was in profile route)
        if len(image_data) > 7_000_000:
            raise ValueError("Image is too large (max 5MB).")
            
        upload_result = cloudinary.uploader.upload(image_data, folder=folder)
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
    if uri and uri.startswith("postgres://"):
        # SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri or 'sqlite:///tum_market.db'

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    # Debugging: Log the connection type to ensure we aren't using a local "ghost" SQLite file
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_mode = "PostgreSQL (Cloud)" if "postgresql" in db_uri else "SQLite (Local File)"
    
    # Security Hardening: Environment Validation
    if not app.debug:
        if app.secret_key == 'tum_market_secret':
            print("🚨 SECURITY WARNING: Using default SECRET_KEY in production!")
        if not os.environ.get('CLOUDINARY_URL') and not os.environ.get('CLOUDINARY_API_KEY'):
            print("🚨 configuration WARNING: Cloudinary credentials missing. Image uploads will fail.")
            
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

@app.route('/api/signup', methods=['POST'])
@limiter.limit("5 per hour") # Prevent account creation spam
def signup():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
        return jsonify({"success": False, "message": "Email is already registered."}), 400

    new_user = User(name=name, email=email, password=generate_password_hash(password))
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
        "profile_picture": None
    })

@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute") # Brute force protection
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

    if user and check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        return jsonify({
            "success": True,
            "message": "Welcome back!",
            "name": user.name,
            "id": user.id,
            "email": user.email,
            "profile_picture": user.profile_picture
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
            "subscription_updated_at": user.subscription_updated_at.isoformat() if user and user.subscription_updated_at else None
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

@app.route('/api/listings', methods=['GET'])
def get_listings():
    listings = db.session.execute(db.select(Listing).filter_by(status='available')).scalars().all()
    available_listings = [
        {"id": l.id, "title": l.title, "price": l.price, "location": l.location, 
         "category": l.category, "image": l.image, "seller_phone": l.seller_phone, 
         "posted_by": l.posted_by, "status": l.status, "tier": l.tier, "views": l.views} for l in listings
    ]
    return jsonify({"success": True, "listings": available_listings})

@app.route('/api/listings', methods=['POST'])
@login_required
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
            unsubscribe_url = f"https://tum-market.onrender.com/api/unsubscribe?email={user.email}"
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
    total_views = sum(l.views or 0 for l in listings)
    
    user_items = [
        {"id": l.id, "title": l.title, "price": l.price, "location": l.location,
         "category": l.category, "seller_phone": l.seller_phone, "image": l.image,
         "status": l.status, "tier": l.tier, "views": l.views} for l in listings
    ]
    return jsonify({"success": True, "listings": user_items, "total_views": total_views})

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

@app.route('/<path:filename>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def serve_static(filename):
    if filename.startswith('api/'):
        return jsonify({"success": False, "message": "Invalid API endpoint."}), 404
    if request.method != 'GET':
        return jsonify({"success": False, "message": "Method not allowed for static files."}), 405

    return send_from_directory(STATIC_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
