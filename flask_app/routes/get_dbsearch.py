import os
from flask import Blueprint, request, jsonify
from flask_app.database import find, delete_one
import subprocess

get_dbsearch_bp = Blueprint('get_dbsearch_bp', __name__)

@get_dbsearch_bp.route('/get_dbsearch', methods=['POST'])
def get_dbsearch():
    taxid = request.json.get('taxid')
    try:
        results_response = find('dbsearch', {'taxid': taxid})
        if results_response['status'] == "success" and results_response['data']:
            results = results_response['data']
            valid_results = []
            for result in results:
                if 'phylogeny_map' not in result['data']:
                    delete_one('dbsearch', {'run_id': result['run_id']})
                else:
                    valid_results.append(result)
            if valid_results:
                data = max(results, key=lambda x: x['date'])
                return jsonify({'status': 'success', 'data': data}), 200
            print("No valid_results")
        return jsonify({'status': 'error', 'message': 'nothing found'}), 200
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500 
    