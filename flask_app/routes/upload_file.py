from flask import Blueprint, request, jsonify
from flask_app.database import update_one
from flask_app.file_ops import create_upload_folder, handle_file_upload, cleanup_old_user_download_folders
from flask_app.process_manager import add_process, remove_process
from flask_app.utils import load_config
import os
import tempfile

upload_file_bp = Blueprint('upload_file_bp', __name__)
config = load_config()

@upload_file_bp.route('/upload_file', methods=['POST'])
def upload_file():
    cleanup_old_user_download_folders()

    # Large multipart uploads may spill to disk; ensure tempfile destination exists.
    tmp_dir = os.environ.get('TMPDIR') or os.path.join(config['BROWNOTATE_PATH'], 'user_download', 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    tempfile.tempdir = tmp_dir

    data = request.form
    run_id = data.get('run_id')
    file_type = data.get('type')
    if not run_id or not file_type:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    process_id = f"upload_file_{run_id}"
    add_process(run_id, process_id, f'upload_file {file_type}', 1)
    try:
        if 'file0' not in request.files:
            return jsonify({'status': 'error', 'message': 'No files found'}), 400
        upload_folder = create_upload_folder()
        file_paths = handle_file_upload(request.files, upload_folder)
        print('file_paths:', file_paths, 'file_type:', file_type)
        if len(file_paths) == 1:
            file_paths = file_paths[0]
        if file_type == "sequencing":
            file_parameters = "parameters.startSection.sequencingFileListOnServer"
        elif file_type == "rna_sequencing":
            file_parameters = "parameters.startSection.rnaSequencingFileListOnServer"
        elif file_type == "assembly":
            file_parameters = "parameters.startSection.assemblyFileOnServer"
        elif file_type == "evidence":
            file_parameters = "parameters.annotationSection.evidenceFileOnServer"
        elif file_type == "protein_fa":
            file_parameters = "parameters.proteinFileOnServer"
        else:
            remove_process(process_id)
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
            remove_process(process_id)
            return jsonify({'status': 'success', 'file_paths': file_paths}), 200
        else:
            remove_process(process_id)
            return jsonify({'status': 'error', 'message': update_result['message']}), 500

    except Exception as e:
        print('upload_file exception')
        error_message = str(e)
        remove_process(process_id)
        return jsonify({'status': 'error', 'message': f"Unexpected error: {error_message}"}), 500
    