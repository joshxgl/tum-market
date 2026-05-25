from flask import Flask, request, jsonify, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
import os
import re
import json
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import cloudinary
import cloudinary.uploader
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tum_market_secret')

# Increase max content length to allow for base64 image uploads (16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

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

# Best Practice: Return JSON errors for Rate Limits
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "success": False, 
        "message": f"Too many requests. Please try again in a moment. {e.description}"
    }), 429

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'sqlite:///tum_market.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
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
    listings = db.relationship('Listing', backref='author', lazy=True)

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True) # Optimized search
    price = db.Column(db.Float, nullable=False, index=True) # Optimized sorting
    location = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True) # Optimized filtering
    image = db.Column(db.Text, nullable=True)
    seller_phone = db.Column(db.String(20), nullable=False)
    posted_by = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True) # Optimized user profile
    status = db.Column(db.String(20), default='available', index=True)
    tier = db.Column(db.String(20), default='free', index=True)
    date_posted = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    type = db.Column(db.String(50))
    title = db.Column(db.String(100))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

with app.app_context():
    db.create_all()

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
            "profile_picture": user.profile_picture if user else None
        })
    return jsonify({"logged_in": False})

@app.route('/api/user/profile-picture', methods=['POST'])
def update_profile_picture():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    image = data.get('image', '').strip()
    if not image or not (image.startswith('data:image/jpeg') or image.startswith('data:image/png')):
        return jsonify({"success": False, "message": "Only PNG and JPEG images are allowed."}), 400
    if len(image) > 7_000_000: # Approx 5MB file in base64
        return jsonify({"success": False, "message": "Image is too large (max 5MB). Please use a smaller photo."}), 400

    user = db.session.get(User, session['user_id'])

    if not user:
        return jsonify({"success": False, "message": "User not found."}), 404

    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(image, folder="tum_market/profiles")
        secure_url = upload_result.get('secure_url')
        
        user.profile_picture = secure_url
        db.session.commit()
        return jsonify({"success": True, "message": "Profile picture updated!", "profile_picture": secure_url})
    except Exception as e:
        app.logger.error(f"Cloudinary Profile Upload Error: {str(e)}")
        return jsonify({"success": False, "message": f"Cloudinary error: {str(e)}"}), 500

@app.route('/api/listings', methods=['GET', 'POST'])
@limiter.limit("5 per minute;20 per hour", methods=["POST"]) # Tiered limit: Burst + Sustain
def handle_listings():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({"success": False, "message": "Unauthorized. Please log in first."}), 401

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

        # Handle Image Upload to Cloudinary
        image_url = None
        if image and image.startswith('data:image/'):
            try:
                upload_result = cloudinary.uploader.upload(image, folder="tum_market/listings")
                image_url = upload_result.get('secure_url')
            except Exception as e:
                app.logger.error(f"Cloudinary Listing Upload Error: {str(e)}")
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

    listings = db.session.execute(db.select(Listing).filter_by(status='available')).scalars().all()
    available_listings = [
        {"id": l.id, "title": l.title, "price": l.price, "location": l.location, 
         "category": l.category, "image": l.image, "seller_phone": l.seller_phone, 
         "posted_by": l.posted_by, "status": l.status, "tier": l.tier} for l in listings
    ]
    return jsonify({"success": True, "listings": available_listings})

@app.route('/api/listings/<int:listing_id>', methods=['PUT', 'DELETE'])
def handle_single_listing(listing_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

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

        image = data.get('image', '').strip()
        if image and image.startswith('data:image/'):
            try:
                upload_result = cloudinary.uploader.upload(image, folder="tum_market/listings")
                target.image = upload_result.get('secure_url')
            except Exception as e:
                app.logger.error(f"Cloudinary Listing Update Error: {str(e)}")
                return jsonify({"success": False, "message": f"Image update error: {str(e)}"}), 500

        db.session.commit()
        return jsonify({"success": True, "message": "Listing updated successfully!"})

@app.route('/api/user/listings', methods=['GET'])
def get_user_listings():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    listings = db.session.execute(db.select(Listing).filter_by(user_id=session['user_id'])).scalars().all()
    user_items = [
        {"id": l.id, "title": l.title, "price": l.price, "location": l.location,
         "category": l.category, "seller_phone": l.seller_phone, "image": l.image,
         "status": l.status, "tier": l.tier} for l in listings
    ]
    return jsonify({"success": True, "listings": user_items})

@app.route('/api/user/listings/clear', methods=['DELETE'])
def clear_user_listings():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    # Efficiently delete all listings belonging to the session user
    db.session.query(Listing).filter_by(user_id=session['user_id']).delete()
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

@app.route('/api/notifications/clear', methods=['DELETE'])
def clear_notifications():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user_id = session['user_id']
    # Instead of deleting, we mark all as read to keep a record, or delete user-specific ones
    stmt = db.update(Notification).where(
        (Notification.user_id == None) | (Notification.user_id == user_id)
    ).values(is_read=True)
    
    db.session.execute(stmt)
    db.session.commit()
    return jsonify({"success": True, "message": "All notifications cleared."})

@app.route('/api/reset_data', methods=['GET', 'POST'])
@app.route('/api/reset_data/', methods=['GET', 'POST'])
def reset_data():
    if request.method == 'GET':
        return jsonify({"success": False, "message": "Method not allowed. Please use POST."}), 405

    # Security: Only allow reset if a secret key matches
    # Set ADMIN_RESET_KEY in your Render environment variables
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != os.environ.get('ADMIN_RESET_KEY', 'lowkey@odis.tumstandard'):
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    with app.app_context():
        db.session.query(Notification).delete()
        db.session.query(Listing).delete()
        db.session.query(User).delete()
        db.session.commit()
    return jsonify({"success": True, "message": "User and listing data has been reset."})


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
