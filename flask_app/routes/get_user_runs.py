from flask import Blueprint, request, jsonify
from flask_app.database import find
from process_manager import check_process

get_user_runs_bp = Blueprint('get_user_runs_bp', __name__)

@get_user_runs_bp.route('/get_user_runs', methods=['POST'])
def get_user_runs():
    user = request.json.get('user')
    if not user:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    runs = find('runs', {'user': user})
    
    if runs['status'] != 'success':
        return jsonify({'status': 'error', 'message': runs['message']}), 500
 
    updated_runs = []
    for run in runs['data']:
        run_id = run['parameters']['id']
        if run['status'] == 'running':
            check_process(run_id)
        updated_runs.append(run)
        
    return jsonify({'status': 'success', 'data': updated_runs}), 200

