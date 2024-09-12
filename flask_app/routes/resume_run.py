
import re
from flask import Blueprint, request, jsonify
from flask_app.database import update_one, find_one
from flask_app.extensions import socketio
from flask_app.commands import build_brownotate_resume_command, run_command

resume_run_bp = Blueprint('resume_run_bp', __name__)

def get_output_run_dir(stdout):
	output_run_dir_match = re.search(r"Your protein annotation is available in (.+?)\. Thank you for using Brownotate", stdout)
	if not output_run_dir_match:
		output_low_rawgenes = re.search(r"Error : Number of genes and rawgenes is too low in the run (.+?), the annotation cannot continue", stdout)
		if output_low_rawgenes:
			return output_low_rawgenes.group(1)
		return None
	return output_run_dir_match.group(1)

def run_failed(stdout, stderr, run_id, message):
	query = {'parameters.id': int(run_id)}
	update = {'$set': {'status': 'failed', 'stdout': stdout, 'stderr' : stderr}}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': run_id, 'status': 'failed', 'stdout': stdout, 'stderr': stderr})
	return jsonify({'status': 'error', 'message': message, 'stderr': stderr, 'stdout': stdout}), 500	

@resume_run_bp.route('/resume_run', methods=['POST'])
def resume_run():
	data = request.json
	run_id = data.get('id')
	if not run_id:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

	query = {'parameters.id': int(run_id)}
	
	# Find the working_dir_id
	result = find_one('runs', query)
	if result['status'] != 'success' or not result['data']:
		return jsonify({'status': 'error', 'message': 'Run not found'}), 404
	run_data = result['data']
	working_dir_id = run_data.get('working_dir_id')
	if not working_dir_id:
		return jsonify({'status': 'error', 'message': 'working_dir_id not found'}), 400

	update = {'$set': {'status': 'running'}}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': run_id, 'status': 'running'})
	command = build_brownotate_resume_command(str(working_dir_id))
	stdout, stderr = run_command(command, str(run_id))

	if stderr:
		return run_failed(stdout, stderr, run_id, "Command failed")
	output_run_dir = get_output_run_dir(stdout)

	if not output_run_dir:
		return run_failed(stdout, stderr, run_id, 'Output directory not found')
	
	if 'Error : Number of genes and rawgenes is too low' in stdout:
		status = 'incomplete'
	else:
		status = 'completed'
	query = {'parameters.id': int(run_id)}
	update = {'$set': {'status': status, 'results_path': output_run_dir, 'stdout': stdout, 'stderr' : stderr}}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': run_id, 'status': status})
	return jsonify({'status': 'success', 'message': 'Script executed and run updated successfully', 'stdout': stdout, 'stderr': stderr}), 200