from flask import Blueprint, request, jsonify
from flask_app.database import find

waiting_time_dbsearch_bp = Blueprint('waiting_time_dbsearch', __name__)

def time_to_seconds(time_str):
    """Convert timer string format (HH:MM:SS or HH:MM:SS:MS) to seconds"""
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    milliseconds = int(parts[3]) if len(parts) > 3 else 0
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

def seconds_to_time(seconds):
    """Convert seconds to human readable format"""
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
    """
    Get waiting time statistics for each database search step.
    Now retrieves timer data from individual collections (taxonomy, uniprot_proteomes, etc.)
    """
    collections = {
        'Taxonomy': 'taxonomy',
        'Uniprot Proteome': 'uniprot_proteomes',
        'ENSEMBL': 'ensembl',
        'NCBI RefSeq': 'refseq',
        'NCBI GenBank': 'genbank',
        'NCBI SRA (DNA Sequencing)': 'dnaseq',
        'Phylogeny': 'phylogeny'
    }
    
    timer_stats = {}
    
    # Query each collection and extract timer values
    for display_name, collection_name in collections.items():
        result = find(collection_name, {})
        
        if result['status'] == 'success' and result['data']:
            timer_values = []
            
            # Extract timer from each document
            for doc in result['data']:
                if 'timer' in doc and doc['timer']:
                    try:
                        seconds = time_to_seconds(doc['timer'])
                        timer_values.append(seconds)
                    except (ValueError, IndexError):
                        # Skip invalid timer values
                        continue
            
            # Calculate min and max if we have valid data
            if timer_values:
                min_time = min(timer_values)
                max_time = max(timer_values)
                timer_stats[display_name] = (seconds_to_time(min_time), seconds_to_time(max_time))
            else:
                timer_stats[display_name] = None
        else:
            timer_stats[display_name] = None
    
    return jsonify({
        'status': 'success',
        'data': timer_stats
    })