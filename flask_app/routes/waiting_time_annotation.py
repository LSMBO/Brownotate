from flask import Blueprint, request, jsonify
from flask_app.database import find

waiting_time_annotation_bp = Blueprint('waiting_time_annotation', __name__)

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

@waiting_time_annotation_bp.route('/waiting_time_annotation', methods=['POST'])
def get_waiting_time_annotation():
    result = find('runs', {})
    if result['status'] != 'success':
        return jsonify({'status': 'error', 'message': 'Failed to retrieve data'}), 500
    
    timer_keys = [
        'Uploading sequencing files ',
        'Downloading sequencing files from SRA ',
        'Running fastp on sequencing files ',
        'Removing Phix from sequencing files ',
        'Running Megahit assembly ',
        'Downloading assembly file from Ensembl FTP ',
        'Downloading assembly file from NCBI ',
        'Uploading assembly file ',
        'Running BUSCO on assembly ',
        'Running Prokka annotation ',
        'Uploading custom evidence files ',
        'Searching for evidences (proteins) in the databases ',
        'Selecting and downloading evidences (proteins) from the database search ',
        'Splitting assembly for annotation ',
        'Running Scipio ',
        'Running gene prediction model ',
        'Optimizing gene prediction model ',
        'Running Augustus annotation ',
        'Removing short sequences from annotation according to the length filter ',
        'Removing redundancy from annotation ',
        'Running Brownaming ',
        'Running BUSCO on annotation '
    ]

    
    # Extract timers of each run, only if 'timers' key exists
    timer_values = {key: [] for key in timer_keys}
    for annotation in result['data']:
        timers = annotation.get('timers')
        if not timers:
            continue
        for timer_key in timer_keys:
            if timer_key in timers and timers[timer_key]:
                seconds = time_to_seconds(timers[timer_key])
                timer_values[timer_key].append(seconds)

    # Calculate min and max for each timer    
    timer_stats = {}
    for timer_key in timer_keys:
        if timer_values[timer_key]:
            min_time = min(timer_values[timer_key])
            max_time = max(timer_values[timer_key])
            timer_stats[timer_key] = (seconds_to_time(min_time), seconds_to_time(max_time))
        else:
            timer_stats[timer_key] = None
    
    return jsonify({
        'status': 'success',
        'data': timer_stats
    })