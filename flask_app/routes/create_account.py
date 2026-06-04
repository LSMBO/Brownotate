import os
import subprocess
import sys

from flask import Blueprint, jsonify, request

from flask_app.database import find_one


create_account_bp = Blueprint('create_account_bp', __name__)

ACCESS_CODE = '255A}qh8UO33'


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _run_database_admin(email, password):
    repo_root = _repo_root()
    script_path = os.path.join(repo_root, 'database_admin.py')
    result = subprocess.run(
        [sys.executable, script_path, '-email', email, '-password', password],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = (result.stdout or '').strip()
    stderr = (result.stderr or '').strip()
    if result.returncode != 0:
        return False, stderr or stdout or 'database_admin.py failed'
    if 'An error occurred:' in stdout:
        return False, stdout
    return True, stdout


@create_account_bp.route('/create_account', methods=['POST'])
def create_account():
    data = request.json or {}
    access_code = (data.get('accessCode') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    confirm_update = bool(data.get('confirmUpdate', False))

    if access_code != ACCESS_CODE:
        return jsonify({'message': 'Invalid access code'}), 403

    if '@' not in email:
        return jsonify({'message': 'Email must contain @'}), 400

    if len(password) < 4:
        return jsonify({'message': 'Password must contain at least 4 characters'}), 400

    existing_user = find_one('users', {'email': email})
    if existing_user['status'] != 'success':
        return jsonify({'message': existing_user.get('message', 'Failed to check account')}), 500

    if existing_user.get('data') and not confirm_update:
        return jsonify({
            'message': 'This email is already used. Do you want to update its password?',
            'emailExists': True,
        }), 409

    ok, output = _run_database_admin(email, password)
    if not ok:
        return jsonify({'message': output or 'Unable to create account'}), 500

    action = 'updated' if existing_user.get('data') else 'created'
    return jsonify({
        'message': f'Account {action} successfully',
        'action': action,
        'details': output,
    }), 200


@create_account_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if '@' not in email:
        return jsonify({'message': 'Email must contain @'}), 400

    if len(password) < 4:
        return jsonify({'message': 'Password must contain at least 4 characters'}), 400

    existing_user = find_one('users', {'email': email})
    if existing_user['status'] != 'success':
        return jsonify({'message': existing_user.get('message', 'Failed to check account')}), 500

    if not existing_user.get('data'):
        return jsonify({'message': 'This email does not exist. Please create an account first.'}), 404

    ok, output = _run_database_admin(email, password)
    if not ok:
        return jsonify({'message': output or 'Unable to reset password'}), 500

    return jsonify({
        'message': 'Password updated successfully',
        'details': output,
    }), 200