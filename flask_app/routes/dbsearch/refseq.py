from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch_mod
from flask_app.database import find, update_one
import json, datetime

dbs_refseq_bp = Blueprint('dbs_refseq_bp', __name__)

@dbs_refseq_bp.route('/dbs_refseq', methods=['POST'])
def dbs_refseq():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'refseq',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    ncbi_refseq_annotated_genomes, ncbi_refseq_genomes = dbsearch_mod.get_ncbi_genomes(output_data['data'], "RefSeq")
    output_data['data']['ncbi_refseq_annotated_genomes'] = ncbi_refseq_annotated_genomes
    output_data['data']['ncbi_refseq_genomes'] = ncbi_refseq_genomes

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'refseq', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
    
    return jsonify(output_data)
