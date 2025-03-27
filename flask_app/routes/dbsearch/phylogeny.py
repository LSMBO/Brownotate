from flask import Blueprint, request, jsonify
import database_search.database_search as dbsearch_mod
from flask_app.database import find, update_one
import json, datetime, os


dbs_phylogeny_bp = Blueprint('dbs_phylogeny_bp', __name__)

@dbs_phylogeny_bp.route('/dbs_phylogeny', methods=['POST'])
def dbs_phylogeny():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')

    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'phylogeny',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }

    phylogeny_map_path = os.path.join('output_runs', dbsearch['run_id'], 'phylogeny_map.png')
    dbsearch_mod.get_phylogeny_map(dbsearch['data'], phylogeny_map_path)
    output_data['data']['phylogeny_map'] = phylogeny_map_path
    
    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'phylogeny', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
    
    return jsonify(output_data)
