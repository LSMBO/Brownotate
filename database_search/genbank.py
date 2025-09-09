from flask import Blueprint, request, jsonify
import database_search.ncbi as ncbi
from flask_app.database import find, update_one
import json
from timer import timer

dbs_genbank_bp = Blueprint('dbs_genbank_bp', __name__)

@dbs_genbank_bp.route('/dbs_genbank', methods=['POST'])
def dbs_genbank():
    start_time = timer.start()
    
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    run_id = request.json.get('run_id', dbsearch['run_id'] if dbsearch else None)

    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'genbank',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    ncbi_genbank_annotated_genomes, ncbi_genbank_genomes = ncbi.get_ncbi_genomes(output_data['data'], "genbank", run_id=run_id)
    output_data['data']['ncbi_genbank_annotated_genomes'] = ncbi_genbank_annotated_genomes
    output_data['data']['ncbi_genbank_genomes'] = ncbi_genbank_genomes

    timer_str = timer.stop(start_time)
    print(f"Timer dbs_genbank: {timer_str}")
    output_data['data']['timer_genbank'] = timer_str

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'genbank', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
    
    return jsonify(output_data)
