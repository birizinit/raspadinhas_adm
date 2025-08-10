from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta
import json
import os
import random
import uuid

app = Flask(__name__)

DATA_FILE = 'data.json'
ADMIN_TOKEN = 'supersecretadmin' # Em um ambiente de produção, use um método mais seguro para tokens/senhas

def load_data():
    if not os.path.exists(DATA_FILE):
        initial_data = {
            "scratch_links": [],
            "daily_data": {
                "last_updated": None,
                "balance": 0,
                "winners": 0,
                "best_times": "Manhã (9h-11h), Noite (20h-22h)",
                "good_moment": False,
                "recommended_link_id": None
            },
            "admin_credentials": {
                "username": "admin",
                "password": "password123" # Em um ambiente de produção, use hash de senhas
            }
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(initial_data, f, indent=4)
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def update_daily_fictitious_data():
    data = load_data()
    daily_data = data['daily_data']
    
    today = datetime.now().date()
    last_updated_str = daily_data.get('last_updated')
    last_updated_date = datetime.strptime(last_updated_str, '%Y-%m-%d').date() if last_updated_str else None

    if not last_updated_date or last_updated_date < today:
        daily_data['balance'] = round(random.uniform(1000.0, 50000.0), 2)
        daily_data['winners'] = random.randint(50, 500)
        
        # Randomly pick a good moment status
        daily_data['good_moment'] = random.choice([True, False])

        # Randomly pick a recommended link
        if data['scratch_links']:
            daily_data['recommended_link_id'] = random.choice(data['scratch_links'])['id']
        else:
            daily_data['recommended_link_id'] = None

        daily_data['last_updated'] = today.strftime('%Y-%m-%d')
        save_data(data)
        print(f"Daily fictitious data updated for {today}")
    return data

# Chame as funções de inicialização diretamente no nível superior do módulo
load_data()
update_daily_fictitious_data()


@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = jsonify({'message': 'CORS preflight success'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        return response

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    return response

def admin_required(f):
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Authorization token is missing!"}), 401
        token = auth_header.split(' ')[1]
        if token != ADMIN_TOKEN:
            return jsonify({"message": "Invalid or expired token!"}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__ # Preserve original function name
    return decorated_function

@app.route('/')
def serve_public_dashboard():
    return send_from_directory('.', 'public-dashboard.html')

@app.route('/admin')
def serve_admin_panel():
    return send_from_directory('.', 'admin-panel.html')

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    data = update_daily_fictitious_data()
    
    # Prepare links for dashboard, including recommended status
    links = data['scratch_links']
    recommended_link_id = data['daily_data']['recommended_link_id']
    
    dashboard_links = []
    for link in links:
        link_copy = link.copy()
        link_copy['is_recommended'] = (link['id'] == recommended_link_id)
        dashboard_links.append(link_copy)

    response_data = {
        "scratch_links": dashboard_links,
        "daily_data": data['daily_data'],
        "total_houses": len(links)
    }
    return jsonify(response_data)

@app.route('/api/links', methods=['GET', 'POST'])
@admin_required
def manage_links():
    data = load_data()
    if request.method == 'GET':
        return jsonify(data['scratch_links'])
    elif request.method == 'POST':
        new_link = request.json
        if not new_link or not all(k in new_link for k in ['house_name', 'link', 'status']):
            return jsonify({"message": "Missing data for new link"}), 400
        new_link['id'] = str(uuid.uuid4())
        data['scratch_links'].append(new_link)
        save_data(data)
        return jsonify(new_link), 201

@app.route('/api/links/<link_id>', methods=['PUT', 'DELETE'])
@admin_required
def manage_single_link(link_id):
    data = load_data()
    links = data['scratch_links']
    link_found = next((link for link in links if link['id'] == link_id), None)

    if not link_found:
        return jsonify({"message": "Link not found"}), 404

    if request.method == 'PUT':
        updated_data = request.json
        if not updated_data:
            return jsonify({"message": "No data provided for update"}), 400
        
        link_found.update(updated_data)
        save_data(data)
        return jsonify(link_found)
    
    elif request.method == 'DELETE':
        data['scratch_links'] = [link for link in links if link['id'] != link_id]
        save_data(data)
        return jsonify({"message": "Link deleted successfully"}), 200

@app.route('/api/daily-data', methods=['GET', 'PUT'])
@admin_required
def manage_daily_data():
    data = load_data()
    if request.method == 'GET':
        return jsonify(data['daily_data'])
    elif request.method == 'PUT':
        updated_data = request.json
        if not updated_data:
            return jsonify({"message": "No data provided for update"}), 400
        
        # Only allow specific fields to be updated
        allowed_fields = ['balance', 'winners', 'best_times', 'good_moment', 'recommended_link_id']
        for field in allowed_fields:
            if field in updated_data:
                data['daily_data'][field] = updated_data[field]
        
        # Ensure recommended_link_id is valid if provided
        if 'recommended_link_id' in updated_data and updated_data['recommended_link_id'] is not None:
            link_exists = any(link['id'] == updated_data['recommended_link_id'] for link in data['scratch_links'])
            if not link_exists:
                return jsonify({"message": "Recommended link ID does not exist"}), 400

        save_data(data)
        return jsonify(data['daily_data'])

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    credentials = request.json
    data = load_data()
    if credentials and credentials.get('username') == data['admin_credentials']['username'] and \
       credentials.get('password') == data['admin_credentials']['password']:
        return jsonify({"message": "Login successful", "token": ADMIN_TOKEN}), 200
    return jsonify({"message": "Invalid credentials"}), 401
