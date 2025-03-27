from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch_mod
from flask_app.database import find, update_one
import json, datetime

dbs_genbank_bp = Blueprint('dbs_genbank_bp', __name__)

@dbs_genbank_bp.route('/dbs_genbank', methods=['POST'])
def dbs_genbank():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')

    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'genbank',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    ncbi_genbank_annotated_genomes, ncbi_genbank_genomes = dbsearch_mod.get_ncbi_genomes(output_data['data'], "genbank")
    output_data['data']['ncbi_genbank_annotated_genomes'] = ncbi_genbank_annotated_genomes
    output_data['data']['ncbi_genbank_genomes'] = ncbi_genbank_genomes

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'genbank', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
    
    return jsonify(output_data)
