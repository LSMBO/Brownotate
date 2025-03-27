from flask import Blueprint, request, jsonify
import requests

check_species_exists_bp = Blueprint('check_species_exists_bp', __name__)

@check_species_exists_bp.route('/check_species_exists', methods=['POST'])
def check_species_exists():
    species = request.json.get('species')
    if not species:
        return jsonify({'status': 'error', 'message': 'Missing species parameter'}), 400

    if (isinstance(species, str) and species.isnumeric()==False):
        species_parts = species.lower().split(' ')
        scientific_name = "%20".join(species_parts)
        url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name}%22)&size=500&format=json"  
    else:
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{species})&size=500&format=json"
        
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json()["results"]
        for result in results:
            scientific_name = result["scientificName"]
            taxon_id = result["taxonId"]
            lineage = result["lineage"]
            if (str(taxon_id) == species or scientific_name.lower() == species.lower()):
                is_bacteria = False
                for taxon in lineage:
                    if taxon["scientificName"] == "Bacteria":
                        is_bacteria = True
                        break
                output_data = {
                    'scientific_name': result["scientificName"],
                    'taxid': result["taxonId"],
                    'lineage': result["lineage"],
                    'is_bacteria': is_bacteria
                }
                return jsonify({'status': 'success', 'results': output_data}), 200

    return jsonify({'status': 'error', 'message': f"\nTaxo \"{species}\" not found."}), 500