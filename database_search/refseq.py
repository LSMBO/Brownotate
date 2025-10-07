from flask import Blueprint, request, jsonify
import database_search.ncbi as ncbi
from flask_app.database import find, update_one
import json
from timer import timer

dbs_refseq_bp = Blueprint('dbs_refseq_bp', __name__)

@dbs_refseq_bp.route('/dbs_refseq', methods=['POST'])
def dbs_refseq():
    start_time = timer.start()
    
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    run_id = request.json.get('run_id', dbsearch['run_id'] if dbsearch else None)
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'refseq',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    try:
        ncbi_refseq_annotated_genomes, ncbi_refseq_genomes = ncbi.get_ncbi_genomes(output_data['data'], "RefSeq", run_id=run_id)
        
        if ncbi_refseq_annotated_genomes is None or ncbi_refseq_genomes is None:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch NCBI RefSeq genomes data',
                'timer': timer.stop(start_time)
            }), 500
            
        output_data['data']['ncbi_refseq_annotated_genomes'] = ncbi_refseq_annotated_genomes
        output_data['data']['ncbi_refseq_genomes'] = ncbi_refseq_genomes

        timer_str = timer.stop(start_time)
        print(f"Timer dbs_refseq: {timer_str}")
        output_data['data']['timer_refseq'] = timer_str

        query = {'run_id': dbsearch['run_id']}
        update = { '$set': {'status': 'refseq', 'data': output_data['data']} }    
        
        if create_new_dbs:
            update_one('dbsearch', query, update)
        
        return jsonify(output_data)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error processing RefSeq data: {str(e)}',
            'timer': timer.stop(start_time)
        }), 500
