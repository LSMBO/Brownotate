from flask import Blueprint, request, jsonify
from flask_app.database import find
from process_manager import check_process, get_cpus_used
import time

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
            time.sleep(5) # It let the time to /run_brownotate to execute the process and add the process to the database
            check_process(run_id)
        updated_runs.append(run)
    cpus = get_cpus_used()
    return jsonify({'status': 'success', 'data': updated_runs, 'cpus': cpus}), 200

