import os
from flask import Blueprint, request, jsonify
from flask_app.database import find
import subprocess

get_dbsearches_bp = Blueprint('get_dbsearches_bp', __name__)

@get_dbsearches_bp.route('/get_dbsearches', methods=['POST'])
def get_dbsearches():
    """
    Get all database search entries, optionally filtered by taxid.
    If no taxid is provided, returns all entries from all collections.
    Returns data grouped by date for each collection.
    """
    taxid = request.json.get('taxid') if request.json else None
    
    try:
        # Build query filter
        query = {'taxid': taxid} if taxid else {}
        
        # Fetch all entries from each collection
        taxonomy_response = find('taxonomy', query)
        uniprot_response = find('uniprot', query)
        ensembl_response = find('ensembl', query)
        refseq_response = find('refseq', query)
        genbank_response = find('genbank', query)
        dnaseq_response = find('dnaseq', query)
        phylogeny_response = find('phylogeny', query)

        result = {
            'status': 'success',
            'taxonomy': taxonomy_response['data'] if taxonomy_response['status'] == 'success' else [],
            'uniprot': uniprot_response['data'] if uniprot_response['status'] == 'success' else [],
            'ensembl': ensembl_response['data'] if ensembl_response['status'] == 'success' else [],
            'refseq': refseq_response['data'] if refseq_response['status'] == 'success' else [],
            'genbank': genbank_response['data'] if genbank_response['status'] == 'success' else [],
            'dnaseq': dnaseq_response['data'] if dnaseq_response['status'] == 'success' else [],
            'phylogeny': phylogeny_response['data'] if phylogeny_response['status'] == 'success' else []
        }
        
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
