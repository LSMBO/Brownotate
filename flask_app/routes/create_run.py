from flask import Blueprint, request, jsonify
from flask_app.database import insert_one
from flask_app.extensions import socketio

create_run_bp = Blueprint('create_run_bp', __name__)

@create_run_bp.route('/create_run', methods=['POST'])
def create_run():
	data = request.json
	user = data.get('user')
	parameters = data.get('parameters')
	if not user or not parameters:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
		
	run_data = {
		'user': user,
		'status': 'upload',
		'parameters': parameters
	}
	insert_result = insert_one('runs', run_data)
	socketio.emit('runs_updated', {'run_id': parameters.id, 'status': 'upload'})
	if insert_result['status'] == 'success':
		run_data['_id'] = str(insert_result['inserted_id'])
		return jsonify({'status': 'success', 'run': run_data}), 200
	else:
		return jsonify({'status': 'error', 'message': insert_result['message']}), 500