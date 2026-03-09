from flask import Blueprint, request, jsonify
from database_search.uniprot_taxo import UniprotTaxo, get_url
from flask_app.database import insert_one
import json, datetime
from timer import timer

dbs_uniprot_bp = Blueprint('dbs_uniprot_bp', __name__)

def get_uniprot_proteome(data):
    proteome = []
    exclude_ids = []
    for taxo in data['lineage']:
        if taxo['rank'] in ['species', 'subspecies', 'strain', 'variety']:
            proteome += UniprotTaxo.search_proteome(taxo['taxonId'])
        else:
            children = UniprotTaxo.get_children_with_proteome(taxo['taxonId'], 3, exclude_ids)
            children_taxids, children_scientific_names = zip(*children) if children else ([], [])
            exclude_ids += children_taxids
            for child in children_taxids:
                proteome += UniprotTaxo.search_proteome(child)
                if len(proteome) >= 3:
                    return proteome[:3]

        if proteome:
            return proteome
    return proteome

@dbs_uniprot_bp.route('/dbs_uniprot', methods=['POST'])
def dbs_uniprot():
    try:
        start_time = timer.start()
        user = request.json.get('user')
        taxonomy = request.json.get('taxonomy')
        options = request.json.get('options', {})
        current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
        if not user or not taxonomy:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400 

        # Get proteomes
        proteome = get_uniprot_proteome(taxonomy)
                
        timer_str = timer.stop(start_time)

        mongo_query = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': {
                'proteome': proteome,
                'statistics': taxonomy['statistics']
            }
        }
        insert_one('uniprot', mongo_query)

        response_data = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': {
                'proteome': proteome,
                'statistics': taxonomy['statistics']
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


# Utility functions for UniProt FASTA downloads
def uniprot_fasta(url):
    file_name="output_testing.fasta"
    r = get_url(url)
    write_fasta(r.text, file_name)
    print(r.links)
    while r.links.get("next", {}).get("url"):
        r = get_url(r.links["next"]["url"])
        write_fasta(r.text, file_name)

def write_fasta(cnt, file_name):
    otp = open(file_name, "a")
    otp.write(cnt)
    otp.close()
