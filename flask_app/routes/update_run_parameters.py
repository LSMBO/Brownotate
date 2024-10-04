from flask import Blueprint, request, jsonify
from flask_app.database import update_one

update_run_parameters_bp = Blueprint('update_run_parameters_bp', __name__)

@update_run_parameters_bp.route('/update_run_parameters', methods=['POST'])
def update_run_parameters():
    data = request.json
    user = data.get('user')
    type = data.get('type')
    urls = data.get('urls')
    run_id = data.get('run_id')
        
    if not user or not urls or not run_id:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    
    if type == 'assembly':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.startSection.genomeFileList": urls['assembly']
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    if type == 'evidence':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.annotationSection.evidenceFileList": urls['evidence']
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200
