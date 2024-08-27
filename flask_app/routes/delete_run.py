from flask import Blueprint, request, jsonify
from flask_app.database import delete_one
from flask_app.extensions import socketio
from flask_app.process_manager import stop_process

delete_run_bp = Blueprint('delete_run_bp', __name__)

@delete_run_bp.route('/delete_run', methods=['POST'])
def delete_run():
    data = request.json
    run_id = data.get('id')
    if not run_id:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    result = delete_one('runs', {'parameters.id': int(run_id)})
    if result['status'] == 'success':
        stop_process(run_id)
        socketio.emit('runs_updated', {'run_id': run_id, 'status': 'deleted'})
        if result.get('deleted_count', 0) > 0:
            return jsonify({'status': 'success', 'message': f'Run {run_id} deleted successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'No run found with the specified ID'}), 404
    else:
        return jsonify(result), 500
