from flask import Blueprint, request, jsonify
from flask_app.database import update_one

update_run_parameters_bp = Blueprint('update_run_parameters_bp', __name__)

@update_run_parameters_bp.route('/update_run_parameters', methods=['POST'])
def update_run_parameters():
    data = request.json
    user = data.get('user')
    data_type = data.get('data_type', None)
    file_list = data.get('file_list')
    run_id = data.get('run_id')
    progress = data.get('progress')
        
    if data_type == 'assembly':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.startSection.assemblyFileOnServer": file_list,
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    if data_type == 'evidence':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.annotationSection.evidenceFileOnServer": file_list,
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    if data_type == 'sequencing':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.startSection.sequencingFileListOnServer": file_list,
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    else:
        jsonify({'status': 'error', 'message': 'Invalid data_type'}), 400
            
    return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200
