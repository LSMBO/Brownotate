from flask import Blueprint, request, jsonify
import database_search.wiki as wiki
from database_search.uniprot import UniprotTaxo


check_species_exists_bp = Blueprint('check_species_exists_bp', __name__)

@check_species_exists_bp.route('/check_species_exists', methods=['POST'])
def check_species_exists():
    species = request.json.get('species')
    if not species:
        return jsonify({'status': 'error', 'message': 'Missing species parameter'}), 400

    taxo = UniprotTaxo(species, run_id='check_species_exists')
    if taxo:
        output_data = taxo.get_taxonomy()
        taxo_image_url = wiki.download_species_image(output_data['scientificName'])
        output_data['taxo_image_url'] = taxo_image_url
        return jsonify({'status': 'success', 'results': output_data}), 200

    return jsonify({'status': 'error', 'message': f"\nTaxo \"{species}\" not found."}), 500