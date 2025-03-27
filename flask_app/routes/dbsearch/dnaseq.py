from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch_mod
from flask_app.database import find, update_one
import json, datetime

dbs_dnaseq_bp = Blueprint('dbs_dnaseq_bp', __name__)

@dbs_dnaseq_bp.route('/dbs_dnaseq', methods=['POST'])
def dbs_dnaseq():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'dnaseq',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    dnaseq = dbsearch_mod.get_dnaseq(output_data['data'])
    output_data['data']['dnaseq'] = dnaseq

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'dnaseq', 'data': output_data['data']} } 
        
    if create_new_dbs:
        update_one('dbsearch', query, update)
        
    return jsonify(output_data)
