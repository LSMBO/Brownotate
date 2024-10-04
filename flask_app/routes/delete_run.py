import os, shutil
from flask import Blueprint, request, jsonify
from flask_app.database import find_one, delete_one
from flask_app.extensions import socketio
from flask_app.process_manager import stop_process
from utils import load_config

delete_run_bp = Blueprint('delete_run_bp', __name__)
config = load_config()

@delete_run_bp.route('/delete_run', methods=['POST'])
def delete_run():
	data = request.json
	run_id = data.get('id')
		
	if not run_id:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
		
	# Find the working_dir_id
	query = {'parameters.id': int(run_id)}
	result = find_one('runs', query)
	if result['status'] != 'success' or not result['data']:
		return jsonify({'status': 'error', 'message': 'Run not found'}), 404
	run_data = result['data']
	working_dir_id = run_data.get('working_dir_id')
 
	result = delete_one('runs', {'parameters.id': int(run_id)})
	if result['status'] == 'success':
		stop_process(run_id)
		socketio.emit('runs_updated', {'run_id': run_id, 'status': 'deleted'})
		if result.get('deleted_count', 0) > 0:
			if working_dir_id:
				working_dir = os.path.join(config['BROWNOTATE_PATH'], 'runs', str(working_dir_id))
				if os.path.exists(working_dir):
					shutil.rmtree(working_dir)
				output_dir = os.path.join(config['BROWNOTATE_PATH'], 'output_runs', str(working_dir_id))
				if os.path.exists(output_dir):
					shutil.rmtree(output_dir)
    
			return jsonify({'status': 'success', 'message': f'Run {run_id} deleted successfully'})
		else:
			return jsonify({'status': 'error', 'message': 'No run found with the specified ID'}), 404
	return jsonify(result), 500


				

