from flask import Blueprint, request, jsonify
import database_search.ncbi as ncbi
from flask_app.database import insert_one
import json, datetime
from timer import timer

dbs_refseq_bp = Blueprint('dbs_refseq_bp', __name__)

@dbs_refseq_bp.route('/dbs_refseq', methods=['POST'])
def dbs_refseq():
    start_time = timer.start()
    user = request.json.get('user')
    taxonomy = request.json.get('taxonomy')
    options = request.json.get('options', {})
    current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
    
    if not user or not taxonomy:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    try:
        ncbi_refseq_annotated_genomes, ncbi_refseq_genomes = ncbi.get_ncbi_genomes(taxonomy, "refseq", run_id=current_datetime)
        if ncbi_refseq_annotated_genomes is None or ncbi_refseq_genomes is None:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch NCBI RefSeq genomes data',
                'timer': timer.stop(start_time)
            }), 500
        timer_str = timer.stop(start_time)
        
        mongo_query = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': {
                'ncbi_refseq_annotated_genomes': ncbi_refseq_annotated_genomes,
                'ncbi_refseq_genomes': ncbi_refseq_genomes
            }
        }
        insert_one('refseq', mongo_query)
        
        response_data = {
            'user': user,
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': {
                'ncbi_refseq_annotated_genomes': ncbi_refseq_annotated_genomes,
                'ncbi_refseq_genomes': ncbi_refseq_genomes
            }
        }
        
        return jsonify({'status': 'success', 'data': response_data}), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'timer': timer.stop(start_time),
            'details': str(e)
        }), 500
