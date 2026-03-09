import os
from flask import Blueprint, request, jsonify
from flask_app.database import find
import subprocess

get_dbsearch_bp = Blueprint('get_dbsearch_bp', __name__)

@get_dbsearch_bp.route('/get_dbsearch', methods=['POST'])
def get_dbsearch():
    taxid = request.json.get('taxid')
    
    try:
        uniprot_response = find('uniprot', {'taxid': taxid})
        ensembl_response = find('ensembl', {'taxid': taxid})
        refseq_response = find('refseq', {'taxid': taxid})
        genbank_response = find('genbank', {'taxid': taxid})
        dnaseq_response = find('dnaseq', {'taxid': taxid})

        result = {
            'status': 'success',
            'uniprot': get_most_recent(uniprot_response),
            'ensembl': get_most_recent(ensembl_response),
            'refseq': get_most_recent(refseq_response),
            'genbank': get_most_recent(genbank_response),
            'dnaseq': get_most_recent(dnaseq_response),
        }
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_most_recent(response):
    if response['status'] == 'success' and response['data']:
        most_recent = max(response['data'], key=lambda x: x.get('date', ''))
        return {
            'status': 'success',
            'data': most_recent
        }
    return {
        'status': 'not_found',
        'data': None
    }