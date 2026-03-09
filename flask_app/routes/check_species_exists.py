from flask import Blueprint, request, jsonify
from flask_app.database import find_one, insert_one
import database_search.wiki as wiki
from database_search.uniprot_taxo import UniprotTaxo
import datetime
from timer import timer


check_species_exists_bp = Blueprint('check_species_exists_bp', __name__)

@check_species_exists_bp.route('/check_species_exists', methods=['POST'])
def check_species_exists():
    try:
        start_time = timer.start()
        scientific_name = request.json.get('species')
        user = request.json.get('user', '')  # Optional user parameter
        current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
        
        if not scientific_name:
            return jsonify({'status': 'error', 'message': 'Missing species parameter'}), 400

        taxonomy_response = find_one('taxonomy', {'scientific_name': scientific_name.lower()})
        if taxonomy_response['status'] == 'success' and taxonomy_response['data']:
            return jsonify({'status': 'success', 'data': taxonomy_response['data']}), 200

        taxo = UniprotTaxo(scientific_name, run_id=current_datetime)
        if taxo:
            taxonomy_data = taxo.get_taxonomy()
            if not taxonomy_data:
                return jsonify({'status': 'error', 'message': f'Could not retrieve taxonomy data for "{scientific_name}"'}), 500
                
            taxo_image_url = wiki.download_species_image(taxonomy_data['scientificName'])
            timer_str = timer.stop(start_time)
            
            mongo_query = {
                'user': user,
                'timer': timer_str,
                'date': current_datetime,
                'scientific_name': taxonomy_data['scientificName'].lower(),
                'taxid': taxonomy_data['taxonId'],
                'taxo_image_url': taxo_image_url,
                'data': taxonomy_data
            }
            
            insert_result = insert_one('taxonomy', mongo_query)
            if insert_result['status'] == 'error':
                print(f"Warning: Failed to insert taxonomy data: {insert_result['message']}")

            response_data = {
                'user': user,
                'timer': timer_str,
                'date': current_datetime,
                'scientific_name': taxonomy_data['scientificName'].lower(),
                'taxid': taxonomy_data['taxonId'],
                'taxo_image_url': taxo_image_url,
                'data': taxonomy_data
            }

            return jsonify({'status': 'success', 'data': response_data}), 200

        return jsonify({'status': 'error', 'message': f"\nTaxo \"{scientific_name}\" not found."}), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'timer': timer.stop(start_time),
            'details': str(e)
        }), 500