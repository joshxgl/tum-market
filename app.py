from flask import Flask, request, jsonify, send_from_directory, session
import os
import json
import datetime

app = Flask(__name__)
app.secret_key = 'tum_market_secret'

# --- Persistent JSON Database Configurations ---
USERS_FILE = 'users.json'
LISTINGS_FILE = 'listings.json'

# Default placeholder listings to populate the app initially
DEFAULT_LISTINGS = [
    { "id": 1, "title": "Single Room near Campus", "price": 4500, "location": "Mshomoroni", "category": "hostels", "image": "https://via.placeholder.com/300x180", "seller_phone": "0712345678", "posted_by": "System" },
    { "id": 2, "title": "Compact Student Rice Cooker", "price": 2200, "location": "Stage ya Chini", "category": "appliances", "image": "https://via.placeholder.com/300x180", "seller_phone": "0789012345", "posted_by": "System" },
    { "id": 3, "title": "Calculus & Linear Algebra Textbook", "price": 800, "location": "TUM Main Campus", "category": "academics", "image": "https://via.placeholder.com/300x180", "seller_phone": "0722222222", "posted_by": "System" },
    { "id": 4, "title": "HP EliteBook Laptop - 8GB RAM", "price": 25000, "location": "TUM Gate", "category": "electronics", "image": "https://via.placeholder.com/300x180", "seller_phone": "0733333333", "posted_by": "System" },
    { "id": 5, "title": "Mini Refined Electric Kettle", "price": 1200, "location": "Mshomoroni", "category": "appliances", "image": "https://via.placeholder.com/300x180", "seller_phone": "0744444444", "posted_by": "System" }
]

# --- Helper Helper File Database Engines ---
def load_users():
    if not os.path.exists(USERS_FILE): return {}
    try:
        with open(USERS_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_users(users_data):
    with open(USERS_FILE, 'w') as f: json.dump(users_data, f, indent=4)

def load_listings():
    if not os.path.exists(LISTINGS_FILE):
        # Create file with defaults if it doesn't exist yet
        save_listings(DEFAULT_LISTINGS)
        return DEFAULT_LISTINGS
    try:
        with open(LISTINGS_FILE, 'r') as f: return json.load(f)
    except: return DEFAULT_LISTINGS

def save_listings(listings_data):
    with open(LISTINGS_FILE, 'w') as f: json.dump(listings_data, f, indent=4)


# --- Frontend Asset Routing ---
@app.route('/')
def home():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


# --- Authentication Endpoints ---
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    users = load_users()
    if email in users:
        return jsonify({"success": False, "message": "This email is already registered."}), 400

    next_id = max([u.get("id", 0) for u in users.values()] or [0]) + 1
    users[email] = {"name": name, "password": password, "id": next_id, "email": email}
    save_users(users)

    session['user_id'] = next_id
    session['user_email'] = email
    session['user_name'] = name

    return jsonify({"success": True, "message": "Account created successfully!", "name": name, "id": next_id, "email": email})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')

    users = load_users()
    user = users.get(email)
    if user and user['password'] == password:
        if 'id' not in user:
            next_id = max([u.get("id", 0) for u in users.values()] or [0]) + 1
            user['id'] = next_id
            users[email] = user
            save_users(users)

        session['user_id'] = user.get('id')
        session['user_email'] = email
        session['user_name'] = user['name']

        return jsonify({"success": True, "message": "Welcome back!", "name": user['name'], "id": user.get('id'), "email": email})
    return jsonify({"success": False, "message": "Invalid credentials."}), 401


# --- Marketplace Ad Management Endpoints ---
@app.route('/api/listings', methods=['GET'])
def get_listings():
    # Always pull fresh records saved on disk
    return jsonify({"success": True, "listings": load_listings()})

@app.route('/api/listings', methods=['POST'])
def create_listing():
    data = request.get_json() or {}
    title = data.get('title')
    price = data.get('price')
    location = data.get('location')
    category = data.get('category')
    image = data.get('image')
    seller_phone = data.get('seller_phone', '0700000000')
    posted_by = data.get('posted_by', 'Anonymous')
    tier = data.get('tier', 'free')

    if not title or not price or not location or not category:
        return jsonify({"success": False, "message": "Missing required item fields."}), 400

    listings = load_listings()

    # Create a safe sequential id even when older listings were deleted.
    next_listing_id = max([item.get("id", 0) for item in listings] or [0]) + 1
    current_time = datetime.datetime.now().isoformat()
    user_id = data.get('user_id')
    try:
        user_id = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id = None

    if user_id is None:
        return jsonify({"success": False, "message": "A valid user_id is required to create a listing."}), 400

    new_ad = {
        "id": next_listing_id,
        "title": title,
        "price": int(price),
        "location": location,
        "category": category,
        "image": image if image else "https://via.placeholder.com/300x180",
        "seller_phone": seller_phone,
        "posted_by": posted_by,
        "user_id": user_id,
        "tier": tier,
        "date_posted": current_time
    }

    listings.insert(0, new_ad)
    save_listings(listings)

    return jsonify({"success": True, "message": "Ad posted successfully!", "listing": new_ad})

@app.route('/api/listings/<int:listing_id>/sold', methods=['PATCH'])
def mark_listing_sold(listing_id):
    current_user_id = session.get('user_id')
    if current_user_id is None:
        return jsonify({"success": False, "message": "Unauthorized. Please log in first."}), 401

    listings = load_listings()
    target_item = next((item for item in listings if item['id'] == listing_id), None)
    if not target_item:
        return jsonify({"success": False, "message": "Listing not found."}), 404

    if target_item.get('user_id') != current_user_id:
        return jsonify({"success": False, "message": "Permission denied. You can only mark your own listing as sold."}), 403

    target_item['sold'] = True
    save_listings(listings)

    return jsonify({"success": True, "message": "Listing marked as sold."})

@app.route('/api/listings/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    current_user_id = session.get('user_id')
    if current_user_id is None:
        return jsonify({"success": False, "message": "Unauthorized. Please log in first."}), 401
        
    listings = load_listings()
    
    # Find the target listing
    target_item = next((item for item in listings if item['id'] == listing_id), None)
    
    if not target_item:
        return jsonify({"success": False, "message": "Listing not found."}), 404
        
    if target_item.get('user_id') != current_user_id:
        return jsonify({"success": False, "message": "Permission denied. You can only delete your own posts!"}), 403

    listings = [item for item in listings if item['id'] != listing_id]
    save_listings(listings)
    
    return jsonify({"success": True, "message": "Listing deleted successfully."})


@app.route('/api/notifications')
def get_notifications():
    # Make sure 'not.json' is in your project folder
    try:
        with open('not.json', 'r') as f:
            data = json.load(f)
        return jsonify(data)

    except Exception:
        return jsonify([])


# PROFILE PAGE ROUTE
@app.route('/profile')
def profile():
    return send_from_directory('static', 'profile.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000)