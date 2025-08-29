from flask import Blueprint, request, jsonify
from database_search.uniprot import UniprotTaxo
import database_search.wiki as wiki
from flask_app.database import find, insert_one
import json, datetime, os
from timer import timer

dbs_taxonomy_bp = Blueprint('dbs_taxonomy_bp', __name__)

@dbs_taxonomy_bp.route('/dbs_taxonomy', methods=['POST'])
def dbs_taxonomy():
    start_time = timer.start()
    user = request.json.get('user')
    create_new_dbs = request.json.get('createNewDBS')
    dbsearch = request.json.get('dbsearch')
    
    scientific_name = dbsearch['scientific_name']
    taxID = dbsearch['taxid']
    
    current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")

    if not user or not taxID:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    
    run_id = f"DBS-{taxID}-{current_datetime}"
    output_data = {
        'run_id': run_id,
        'status': 'taxonomy',
        'date': current_datetime,
        'data': {}
    }
    taxo = UniprotTaxo(taxID)
    output_data['data']['taxonomy'] = taxo.get_taxonomy()
    taxo_image_url = wiki.download_species_image(output_data['data']['taxonomy']['scientificName'])
    output_data['data']['taxo_image_url'] = taxo_image_url

    timer_str = timer.stop(start_time)
    print(f"Timer dbs_taxonomy: {timer_str}")
    output_data['data']['timer_taxonomy'] = timer_str
    
    mongo_query = {
            'user': user,
            'run_id': run_id,
            'status': 'taxonomy',
            'date': current_datetime,
            'taxid': taxID,
            'scientific_name': scientific_name,
            'data': output_data['data']
        }
    
    if create_new_dbs:
        insert_one('dbsearch', mongo_query)
    
    os.makedirs(os.path.join('output_runs', run_id), exist_ok=True)
    with open(os.path.join('output_runs', run_id, 'Database_Search.json'), 'w') as f:
        json.dump(output_data['data'], f)
    
    return jsonify(output_data)
