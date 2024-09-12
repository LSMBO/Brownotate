import json, datetime, re
from flask import Blueprint, request, jsonify
from flask_app.database import find_one, update_one
from flask_app.commands import build_brownotate_command, run_command
from flask_app.extensions import socketio

run_brownotate_bp = Blueprint('run_brownotate_bp', __name__)

def get_output_run_dir(stdout):
	output_run_dir_match = re.search(r"Your protein annotation is available in (.+?)\. Thank you for using Brownotate", stdout)
	if not output_run_dir_match:
		return None
	return output_run_dir_match.group(1)

@run_brownotate_bp.route('/run_brownotate', methods=['POST'])
def run_brownotate():
	user = request.json.get('user')
	run_id = request.json.get('run_id')
	if not user or not run_id:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

	results = find_one('runs', {'parameters.id': int(run_id)})

	if not results['data']:
		return jsonify({'status': 'error', 'message': 'Run not found in the MongoDB database'}), 400

	parameters = results['data']['parameters']
	current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
	query = {'parameters.id': parameters['id']}
	update = {
		'$set': {
			'parameters': parameters, 
			'status': 'running',
			'working_dir_id': current_datetime
		}
	}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': run_id, 'status': 'running'})
 
	
	command = build_brownotate_command(parameters, current_datetime)
	stdout, stderr = run_command(command, run_id)
 
	if stderr:
		query = {'parameters.id': parameters['id']}
		update = {'$set': {'status': 'failed', 'stdout': stdout, 'stderr' : stderr}}
		update_one('runs', query, update)
		socketio.emit('runs_updated', {'run_id': run_id, 'status': 'failed', 'stdout': stdout, 'stderr': stderr})
		return jsonify({'status': 'error', 'message': 'Command failed', 'stderr': stderr, 'stdout': stdout}), 500

	output_run_dir = get_output_run_dir(stdout)
	if not output_run_dir:
		return jsonify({'status': 'error', 'message': 'Nothing found for get_output_run_dir_match()'}), 400
	
	query = {'parameters.id': parameters['id']}
	update = {'$set': {'status': 'completed', 'results_path': output_run_dir, 'stdout': stdout, 'stderr' : stderr}}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': parameters['id'], 'status': 'completed'})
	return jsonify({'status': 'success', 'message': 'Script executed and run updated successfully', 'stdout': stdout, 'stderr': stderr}), 200