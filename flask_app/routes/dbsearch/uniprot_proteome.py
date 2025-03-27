from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch_mod
from flask_app.database import find, update_one
import json, datetime

dbs_uniprot_proteome_bp = Blueprint('dbs_uniprot_proteome_bp', __name__)

@dbs_uniprot_proteome_bp.route('/dbs_uniprot_proteome', methods=['POST'])
def dbs_uniprot_proteome():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'uniprot_proteome',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    proteomes = dbsearch_mod.get_uniprot_proteomes(output_data['data'])
    output_data['data']['uniprot_proteomes'] = proteomes

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'uniprot_proteome', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
 
    return jsonify(output_data)
