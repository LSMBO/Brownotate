from flask import Blueprint, request, jsonify
from database_search.uniprot import UniprotTaxo
from flask_app.database import find, update_one
import json
from timer import timer

dbs_uniprot_proteome_bp = Blueprint('dbs_uniprot_proteome_bp', __name__)

def get_uniprot_proteomes(data):
    proteomes = []
    exclude_ids = []
    for taxo in data['taxonomy']['lineage']:
        if taxo['rank'] in ['species', 'subspecies', 'strain', 'variety']:
            proteomes += UniprotTaxo.search_proteome(taxo['taxonId'])
        else:
            children = UniprotTaxo.get_children_with_proteome(taxo['taxonId'], 3, exclude_ids)
            children_taxids, children_scientific_names = zip(*children) if children else ([], [])
            exclude_ids += children_taxids
            for child in children_taxids:
                proteomes += UniprotTaxo.search_proteome(child)
                if len(proteomes) >= 3:
                    return proteomes[:3]

        if proteomes:
            return proteomes
    return proteomes
   
@dbs_uniprot_proteome_bp.route('/dbs_uniprot_proteome', methods=['POST'])
def dbs_uniprot_proteome():
    start_time = timer.start()
    
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'uniprot_proteome',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }
 
    proteomes = get_uniprot_proteomes(output_data['data'])
    output_data['data']['uniprot_proteomes'] = proteomes

    timer_str = timer.stop(start_time)
    print(f"Timer dbs_uniprot_proteome: {timer_str}")
    output_data['data']['timer_uniprot_proteome'] = timer_str

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'uniprot_proteome', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
 
    return jsonify(output_data)
