from flask import Blueprint, request, jsonify
from flask_app.database import find_one

get_run_bp = Blueprint('get_run_bp', __name__)

@get_run_bp.route('/get_run', methods=['POST'])
def get_user_runs():
    run_id = request.json.get('run_id')
    if not run_id:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    run = find_one('runs', {'parameters.id': int(run_id)})
        
    if run['status'] != 'success':
        return jsonify({'status': 'error', 'message': run['message']}), 500

    return jsonify({'status': 'success', 'data': run['data']}), 200

