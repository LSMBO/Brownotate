from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch
from flask_app.database import find, insert_one
import json, datetime, os

dbs_taxonomy_bp = Blueprint('dbs_taxonomy_bp', __name__)

@dbs_taxonomy_bp.route('/dbs_taxonomy', methods=['POST'])
def dbs_taxonomy():
    user = request.json.get('user')
    scientific_name = request.json.get('scientificName')
    taxID = request.json.get('taxid')
    create_new_dbs = request.json.get('createNewDBS')
    current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")

    if not user or not taxID:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    
    run_id = f"DBS-{taxID}-{current_datetime}"
    output_data = {
        'run_id': run_id,
        'status': 'taxonomy',
        'date': current_datetime,
        'data': {}
    }
    taxo = dbsearch.create_taxo(taxID)
    output_data['data']['taxonomy'] = taxo.get_taxonomy()
    mongo_query = {
            'user': user,
            'run_id': run_id,
            'status': 'taxonomy',
            'date': current_datetime,
            'taxid': taxID,
            'scientific_name': scientific_name,
            'data': output_data['data']
        }
    
    if create_new_dbs:
        insert_one('dbsearch', mongo_query)
    
    os.makedirs(os.path.join('output_runs', run_id), exist_ok=True)
    with open(os.path.join('output_runs', run_id, 'Database_Search.json'), 'w') as f:
        json.dump(output_data['data'], f)
    
    return jsonify(output_data)
