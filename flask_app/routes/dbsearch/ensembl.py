from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch_mod
from flask_app.database import find, update_one
import json, datetime

dbs_ensembl_bp = Blueprint('dbs_ensembl_bp', __name__)

@dbs_ensembl_bp.route('/dbs_ensembl', methods=['POST'])
def dbs_ensembl():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'ensembl',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    ensembl_genomes, ensembl_annotated_genomes = dbsearch_mod.get_ensembl(output_data['data'])
    output_data['data']['ensembl_annotated_genomes'] = ensembl_annotated_genomes
    output_data['data']['ensembl_genomes'] = ensembl_genomes

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'ensembl', 'data': output_data['data']} } 
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
        
    return jsonify(output_data)
