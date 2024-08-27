from flask import Blueprint, request, jsonify
from flask_app.database import find_one

login_bp = Blueprint('login_bp', __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    user = find_one('users', {'email', email})
    if user:
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid email'}), 200   