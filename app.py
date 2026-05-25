from flask import Flask, request, jsonify, send_from_directory, session
import os
import json
import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tum_market_secret')

STATIC_FOLDER = 'static'
USERS_FILE = 'users.json'
LISTINGS_FILE = 'listings.json'

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_listings():
    if not os.path.exists(LISTINGS_FILE):
        return []
    try:
        with open(LISTINGS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

def save_listings(listings):
    with open(LISTINGS_FILE, 'w') as f:
        json.dump(listings, f, indent=4)

@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/profile')
def profile_page():
    return send_from_directory(STATIC_FOLDER, 'profile.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    users = load_users()
    if email in users:
        return jsonify({"success": False, "message": "Email is already registered."}), 400

    user_id = max([u.get('id', 0) for u in users.values()], default=0) + 1
    users[email] = {"name": name, "password": password, "id": user_id, "email": email}
    save_users(users)

    session['user_id'] = user_id
    session['user_name'] = name
    session['user_email'] = email

    return jsonify({
        "success": True,
        "message": "Account created successfully!",
        "name": name,
        "id": user_id,
        "email": email,
        "profile_picture": None
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    users = load_users()
    user = users.get(email)

    if user and user.get('password') == password:
        user_email = user.get('email', email)
        if not user.get('email'):
            user['email'] = user_email
            users[email] = user
            save_users(users)
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user_email
        return jsonify({
            "success": True,
            "message": "Welcome back!",
            "name": user['name'],
            "id": user['id'],
            "email": user_email,
            "profile_picture": user.get('profile_picture')
        })

    return jsonify({"success": False, "message": "Invalid email or password."}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route('/api/user/session', methods=['GET'])
def get_session():
    if 'user_id' in session:
        users = load_users()
        user = next((u for u in users.values() if u.get('id') == session['user_id']), None)
        return jsonify({
            "logged_in": True,
            "id": session['user_id'],
            "name": session['user_name'],
            "email": session['user_email'],
            "profile_picture": user.get('profile_picture') if user else None
        })
    return jsonify({"logged_in": False})

@app.route('/api/user/profile-picture', methods=['POST'])
def update_profile_picture():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    image = data.get('image', '').strip()
    if not image or not image.startswith('data:image/'):
        return jsonify({"success": False, "message": "Please upload a valid image file."}), 400
    if len(image) > 2_500_000:
        return jsonify({"success": False, "message": "Image is too large. Please use a smaller photo."}), 400

    users = load_users()
    updated = False
    for email, user in users.items():
        if user.get('id') == session['user_id']:
            user['profile_picture'] = image
            users[email] = user
            updated = True
            break

    if not updated:
        return jsonify({"success": False, "message": "User not found."}), 404

    save_users(users)
    return jsonify({"success": True, "message": "Profile picture updated!", "profile_picture": image})

@app.route('/api/listings', methods=['GET', 'POST'])
def handle_listings():
    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({"success": False, "message": "Unauthorized. Please log in first."}), 401

        data = request.get_json() or {}
        listings = load_listings()

        new_id = max([item['id'] for item in listings], default=0) + 1
        new_item = {
            "id": new_id,
            "title": data.get('title'),
            "price": data.get('price'),
            "location": data.get('location'),
            "category": data.get('category'),
            "image": data.get('image') or "https://via.placeholder.com/300x180",
            "seller_phone": data.get('seller_phone', '0700000000'),
            "posted_by": session['user_name'],
            "user_id": session['user_id'],
            "status": "available",
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        listings.append(new_item)
        save_listings(listings)
        return jsonify({"success": True, "message": "Listing posted successfully!"})

    listings = load_listings()
    available_listings = [item for item in listings if item.get('status', 'available') == 'available']
    return jsonify({"success": True, "listings": available_listings})

@app.route('/api/user/listings', methods=['GET'])
def get_user_listings():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    listings = load_listings()
    user_items = [item for item in listings if item.get('user_id') == session['user_id']]
    return jsonify({"success": True, "listings": user_items})

@app.route('/api/listings/<int:listing_id>/sold', methods=['POST', 'PATCH'])
def mark_as_sold_api(listing_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    listings = load_listings()
    found = False
    for item in listings:
        if item['id'] == listing_id:
            if item.get('user_id') == session['user_id']:
                item['status'] = 'sold'
                found = True
                break
            return jsonify({"success": False, "message": "Permission denied."}), 403

    if not found:
        return jsonify({"success": False, "message": "Item not found."}), 404

    save_listings(listings)
    return jsonify({"success": True, "message": "Item successfully marked as sold!"})

@app.route('/api/listings/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    listings = load_listings()
    target = next((item for item in listings if item['id'] == listing_id), None)

    if not target:
        return jsonify({"success": False, "message": "Listing not found."}), 404
    if target.get('user_id') != session['user_id']:
        return jsonify({"success": False, "message": "Permission denied."}), 403

    listings = [item for item in listings if item['id'] != listing_id]
    save_listings(listings)
    return jsonify({"success": True, "message": "Listing deleted successfully."})

@app.route('/api/notifications')
def get_notifications():
    if not os.path.exists('not.json'):
        return jsonify([])
    try:
        with open('not.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data if isinstance(data, list) else [])
    except (json.JSONDecodeError, OSError):
        return jsonify([])

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
