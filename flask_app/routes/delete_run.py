import os, shutil
from flask import Blueprint, request, jsonify
from flask_app.database import find_one, delete_one
from flask_app.process_manager import stop_run_processes
from utils import load_config

delete_run_bp = Blueprint('delete_run_bp', __name__)
config = load_config()

@delete_run_bp.route('/delete_run', methods=['POST'])
def delete_run():
	data = request.json
	run_id = data.get('id')
		
	if not run_id:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
	find_run_results = find_one('runs', {'parameters.id': int(run_id)})
	delete_result = delete_one('runs', {'parameters.id': int(run_id)})
	if delete_result['status'] == 'success':
		stop_run_processes(run_id)
		if delete_result.get('deleted_count', 0) > 0:
			working_dir = os.path.join(config['BROWNOTATE_PATH'], 'runs', str(run_id))
			if os.path.exists(working_dir):
				shutil.rmtree(working_dir)
			else:
				output_dir = find_run_results['data']['results_path']
				if os.path.exists(output_dir):
					shutil.rmtree(output_dir)
	
			return jsonify({'status': 'success', 'message': f'Run {run_id} deleted successfully'})
		else:
			return jsonify({'status': 'error', 'message': 'No run found with the specified ID'}), 404
	return jsonify(result), 500




