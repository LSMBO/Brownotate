from flask import Blueprint, request, jsonify
from flask_app.database import insert_one
from flask_app.file_ops import create_wd_folder

create_run_bp = Blueprint('create_run_bp', __name__)

@create_run_bp.route('/create_run', methods=['POST'])
def create_run():
	data = request.json
	run_id = data.get('run_id')
	cpus = data.get('cpus')
	user = data.get('user')
	step_list = data.get('stepList')
	parameters = data.get('parameters')
 
	if not user or not parameters or not run_id or not step_list:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
	parameters['id'] = run_id
	parameters['cpus'] = cpus
	run_data = {
		'user': user,
		'status': 'running',
		'progress': ['Run created'],
		'parameters': parameters,
		'run_id': run_id,
		'stepList': step_list,
		'timers': {},
	}

	insert_result = insert_one('runs', run_data)

	# create working directory
	wd_folder = create_wd_folder(run_id)
	
 
	if insert_result['status'] == 'success':
		run_data['_id'] = str(insert_result['inserted_id'])
		return jsonify({'status': 'success', 'run': run_data}), 200
	else:
		return jsonify({'status': 'error', 'message': insert_result['message']}), 500