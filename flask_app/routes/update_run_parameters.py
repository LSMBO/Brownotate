from flask import Blueprint, request, jsonify
from flask_app.database import update_one
import os
import shutil

update_run_parameters_bp = Blueprint('update_run_parameters_bp', __name__)


def _repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _normalize_input_path(path_value):
    if not isinstance(path_value, str):
        return None
    path_value = path_value.strip()
    if len(path_value) >= 2 and ((path_value[0] == '"' and path_value[-1] == '"') or (path_value[0] == "'" and path_value[-1] == "'")):
        path_value = path_value[1:-1]
    return path_value.strip()


def _make_relative_to_repo(path_value):
    repo = _repo_root()
    abs_path = os.path.abspath(path_value)
    if abs_path.startswith(repo + os.sep):
        return os.path.relpath(abs_path, repo)
    return abs_path


def _unique_destination(path_value):
    if not os.path.exists(path_value):
        return path_value

    base, ext = os.path.splitext(path_value)
    idx = 1
    while True:
        candidate = f"{base}_{idx}{ext}"
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def _move_file_to_run_subdir(source_path, run_id, subdir):
    return _move_file_to_run_subdir_as(source_path, run_id, subdir, os.path.basename(source_path))


def _move_file_to_run_subdir_as(source_path, run_id, subdir, target_filename):
    repo = _repo_root()
    source_abs = os.path.abspath(source_path)
    run_subdir_abs = os.path.join(repo, 'runs', str(run_id), subdir)
    os.makedirs(run_subdir_abs, exist_ok=True)

    target_abs = os.path.join(run_subdir_abs, target_filename)
    target_abs = _unique_destination(target_abs)

    if source_abs == target_abs:
        return _make_relative_to_repo(target_abs)

    shutil.move(source_abs, target_abs)
    return _make_relative_to_repo(target_abs)


@update_run_parameters_bp.route('/update_run_parameters', methods=['POST'])
def update_run_parameters():
    data = request.json
    user = data.get('user')
    data_type = data.get('data_type', None)
    file_list = data.get('file_list', None)
    run_id = data.get('run_id')
    progress = data.get('progress', None)
    if data_type == 'assembly':
        assembly_path = file_list[0] if isinstance(file_list, list) and len(file_list) == 1 else file_list
        assembly_path = _normalize_input_path(assembly_path)
        if not isinstance(assembly_path, str) or not assembly_path:
            return jsonify({'status': 'error', 'message': 'Invalid assembly file path'}), 400
        if not os.path.exists(assembly_path):
            return jsonify({'status': 'error', 'message': f'Assembly file does not exist: {assembly_path}'}), 400
        if os.path.getsize(assembly_path) <= 0:
            return jsonify({'status': 'error', 'message': f'Assembly file is empty: {assembly_path}'}), 400

        assembly_in_run = assembly_path
        source_rel = _make_relative_to_repo(assembly_path)
        if source_rel.startswith('user_download' + os.sep):
            assembly_in_run = _move_file_to_run_subdir(assembly_path, run_id, 'assembly')

        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.startSection.assemblyFileOnServer": assembly_in_run,
            }
        }

        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500
        return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200
    
    if data_type == 'evidence':
        # Evidence must be a non-empty file path before we persist it for Scipio.
        evidence_path = file_list[0] if isinstance(file_list, list) and len(file_list) == 1 else file_list
        evidence_path = _normalize_input_path(evidence_path)
        if not isinstance(evidence_path, str) or not evidence_path.strip():
            return jsonify({'status': 'error', 'message': 'Invalid evidence file path'}), 400
        evidence_path = evidence_path.strip()
        if not os.path.exists(evidence_path):
            return jsonify({'status': 'error', 'message': f'Evidence file does not exist: {evidence_path}'}), 400
        if os.path.getsize(evidence_path) <= 0:
            return jsonify({'status': 'error', 'message': f'Evidence file is empty: {evidence_path}'}), 400

        evidence_in_run = evidence_path
        original_filename = os.path.basename(evidence_path)
        source_rel = _make_relative_to_repo(evidence_path)
        if source_rel.startswith('uploads' + os.sep):
            evidence_in_run = _move_file_to_run_subdir_as(
                evidence_path, run_id, 'evidence', 'evidence.fasta'
            )

        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.annotationSection.evidenceFileOnServer": evidence_in_run,
                "parameters.annotationSection.evidenceOriginalFilename": original_filename,
            }
        }
        
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500
        return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200

    if data_type == 'evidence_metadata':
        metadata = data.get('metadata', {}) or {}
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.annotationSection.evidenceSelectionMode": metadata.get('mode'),
                "parameters.annotationSection.evidenceSourceFiles": metadata.get('source_files', []),
                "parameters.annotationSection.selectedEvidenceEntries": metadata.get('selected_entries', []),
            }
        }

        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500
        return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200
    
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
        return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200

    if data_type == 'rna_sequencing':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.startSection.rnaSequencingFileListOnServer": file_list,
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500
        return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200

    if data_type == 'protein_fa':
        query = {
            "parameters.id": int(run_id)
        }
        update = {
            "$set": {
                "parameters.proteinFileOnServer": file_list,
            }
        }
        update_result = update_one('runs', query, update)
        if update_result['status'] != 'success':
            return jsonify({'status': 'error', 'message': update_result['message']}), 500
        return jsonify({'status': 'success', 'message': 'Run parameters updated successfully'}), 200
    
    else:
        return jsonify({'status': 'error', 'message': 'Invalid data_type'}), 400
            
    
