from flask import Blueprint, request, jsonify
from database_search.uniprot_taxo import UniprotTaxo
import database_search.wiki as wiki
from flask_app.database import find, insert_one
import json, datetime, os
from timer import timer

dbs_taxonomy_bp = Blueprint('dbs_taxonomy_bp', __name__)

@dbs_taxonomy_bp.route('/dbs_taxonomy', methods=['POST'])
def dbs_taxonomy():
    try:
        start_time = timer.start()
        user = request.json.get('user')
        taxonomy = request.json.get('taxonomy')
        scientific_name = taxonomy['scientificName']
        taxID = taxonomy['taxonId']
        current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")

        if not user or not taxID:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        taxo = UniprotTaxo(taxID, run_id=current_datetime)
        taxonomy_data = taxo.get_taxonomy()
        taxo_image_url = wiki.download_species_image(taxonomy_data['scientificName'])
        timer_str = timer.stop(start_time)

        mongo_query = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': scientific_name,
            'taxid': taxID,
            'taxo_image_url': taxo_image_url,
            'data': taxonomy_data
        }

        insert_one('taxonomy', mongo_query)
        
        response_data = {
            'user': user,
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': scientific_name,
            'taxid': taxID,
            'taxo_image_url': taxo_image_url,
            'data': taxonomy_data
        }
        
        return jsonify({'status': 'success', 'data': response_data}), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'timer': timer.stop(start_time),
            'details': str(e)
        }), 500
