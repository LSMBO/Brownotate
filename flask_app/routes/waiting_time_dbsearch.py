from flask import Blueprint, request, jsonify
from flask_app.database import find

waiting_time_dbsearch_bp = Blueprint('waiting_time_dbsearch', __name__)

def time_to_seconds(time_str):
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    milliseconds = int(parts[3]) if len(parts) > 3 else 0
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

def seconds_to_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

@waiting_time_dbsearch_bp.route('/waiting_time_dbsearch', methods=['POST'])
def get_waiting_time_dbsearch():
    result = find('dbsearch', {})
    if result['status'] != 'success':
        return jsonify({'status': 'error', 'message': 'Failed to retrieve data'}), 500
    
    timer_keys = [
        'timer_dnaseq',
        'timer_ensembl', 
        'timer_genbank',
        'timer_refseq',
        'timer_taxonomy',
        'timer_uniprot_proteome',
        'timer_phylogeny'
    ]
    
    output_keys = {
        'timer_dnaseq': 'NCBI SRA (DNA Sequencing)',
        'timer_ensembl': 'ENSEMBL',
        'timer_genbank': 'NCBI GenBank',
        'timer_refseq': 'NCBI RefSeq',
        'timer_taxonomy': 'Taxonomy',
        'timer_uniprot_proteome': 'Uniprot Proteome',
        'timer_phylogeny': 'Phylogeny'
    }
    
    # Extract timers of each dbsearch run
    timer_values = {key: [] for key in timer_keys}
    for doc in result['data']:
        doc = doc['data']
        for timer_key in timer_keys:
            if timer_key in doc and doc[timer_key]:
                seconds = time_to_seconds(doc[timer_key])
                timer_values[timer_key].append(seconds)    

    # Calculate min and max for each timer    
    timer_stats = {}
    for timer_key in timer_keys:
        if timer_values[timer_key]:
            min_time = min(timer_values[timer_key])
            max_time = max(timer_values[timer_key])
            timer_stats[output_keys[timer_key]] = (seconds_to_time(min_time), seconds_to_time(max_time))
        else:
            timer_stats[output_keys[timer_key]] = None
    
    return jsonify({
        'status': 'success',
        'data': timer_stats
    })