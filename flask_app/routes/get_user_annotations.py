from flask import Blueprint, request, jsonify
from flask_app.database import find
from process_manager import check_process, get_cpus_used

get_user_annotations_bp = Blueprint('get_user_annotations_bp', __name__)

@get_user_annotations_bp.route('/get_user_annotations', methods=['POST'])
def get_user_annotations():
    user = request.json.get('user')
    check_processes = request.json.get('check_processes')
    if not user:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    annotations = find('runs', {'user': user})
    
    if annotations['status'] != 'success':
        return jsonify({'status': 'error', 'message': annotations['message']}), 500
 
    updated_annotations = []
    progress_not_using_process = ["Downloading assembly file from Ensembl FTP ...", 
                                  "Downloading assembly file from NCBI ...", 
                                  "Searching for evidences (proteins) in the databases ...",
                                  "Selecting and downloading evidences (proteins) from the database search ..."]
    for annotation in annotations['data']:
        run_id = annotation['parameters']['id']
        if check_processes and annotation['status'] == 'running' and annotation['progress'][-1] not in progress_not_using_process and not user.startswith('workshop-cjfps'):
            process_found = check_process(run_id)
            if not process_found:
                annotation['status'] = 'failed'
                
        updated_annotations.append(annotation)

    return jsonify({'status': 'success', 'data': updated_annotations}), 200

