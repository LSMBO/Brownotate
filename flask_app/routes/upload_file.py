from flask import Blueprint, request, jsonify
from flask_app.database import update_one
from flask_app.file_ops import create_upload_folder, handle_file_upload

upload_file_bp = Blueprint('upload_file_bp', __name__)

@upload_file_bp.route('/upload_file', methods=['POST'])
def upload_file():
    data = request.form
    run_id = data.get('run_id')
    file_type = data.get('type')
    if not run_id or not file_type:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    
    try:
        if 'file0' not in request.files:
            return jsonify({'status': 'error', 'message': 'No files found'}), 400
        upload_folder = create_upload_folder()
        file_paths = handle_file_upload(request.files, upload_folder)
        if len(file_paths) == 1:
            file_paths = file_paths[0]
        if file_type == "sequencing":
            file_parameters = "parameters.startSection.sequencingFileListOnServer"
        elif file_type == "assembly":
            file_parameters = "parameters.startSection.assemblyFileOnServer"
        elif file_type == "evidence":
            file_parameters = "parameters.annotationSection.evidenceFileOnServer"
        else:
            return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400

        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                file_parameters: file_paths
            }
        }
        
        update_result = update_one('runs', query, update)
        if update_result['status'] == 'success':
            return jsonify({'status': 'success', 'file_paths': file_paths}), 200
        else:
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    except Exception as e:
        error_message = str(e)
        return jsonify({'status': 'error', 'message': f"Unexpected error: {error_message}"}), 500
