from flask import Blueprint, request, jsonify
from flask_app.database import find_one
import bcrypt

login_bp = Blueprint('login_bp', __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    user = find_one('users', {'email': email})
    if user['status'] == 'success':
        password_hash = user['data']['password_hash'].encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), password_hash):
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'message': 'Invalid email or password'}), 401
    else:
        return jsonify({'message': 'Invalid email or password'}), 401