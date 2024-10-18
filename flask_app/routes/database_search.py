import json, datetime
from flask import Blueprint, request, jsonify
from flask_app.database import find, insert_one
from flask_app.commands import build_dbsearch_command, run_command

database_search_bp = Blueprint('database_search_bp', __name__)

@database_search_bp.route('/database_search', methods=['POST'])
def database_search():
	user = request.json.get('user')
	scientific_name = request.json.get('scientificName')
	taxID = request.json.get('taxID')
	force_new_search = request.json.get('force_new_search')
	current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")

	if not user or not taxID:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

	if not force_new_search:
		mongo_request = find('dbsearch', {'taxID': taxID})
		if mongo_request['status'] == 'success' and mongo_request['data']:
			sorted_requests = sorted(mongo_request['data'], key=lambda x: datetime.datetime.strptime(x['date'], "%d%m%Y-%H%M%S"), reverse=True)
			most_recent_request = sorted_requests[0]
			return jsonify(most_recent_request)
	run_id = f"DBS-{current_datetime}"
	command = build_dbsearch_command(taxID, run_id)
	stdout, stderr = run_command(command, run_id)
	if stderr:
		return jsonify({'status': 'error', 'stdout': stdout, 'stderr': stderr}), 500

	dbsearch_file = f"output_runs/DBS-{current_datetime}/Database_Search.json"
	with open(dbsearch_file, 'r') as file:
		results = json.load(file)
		mongo_query = {
				'result': results,
				'user': user,
				'path': dbsearch_file,
				'scientific_name': scientific_name,
				'taxID': taxID,
				'date': current_datetime
			}
		insert_one('dbsearch', mongo_query)
		return jsonify({
			'status': 'success',
			'data': {
				'user': user,
				'scientific_name': scientific_name,
				'taxID': taxID,
				'path': dbsearch_file,
				'result': results,
				'date': current_datetime
			}
		})
