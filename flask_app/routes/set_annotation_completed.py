from flask import Blueprint, request, jsonify
from flask_app.database import update_one, find_one
from flask_app.file_ops import move_wd_to_output_runs_folder
from flask_app.parameters_report import write_parameters_report, detect_brownotate_version
import os
import shutil

set_annotation_completed_bp = Blueprint('update_set_annotation_completed_bp', __name__)

@set_annotation_completed_bp.route('/set_annotation_completed', methods=['POST'])
def set_annotation_completed():
    data = request.json
    run_id = data.get('run_id')
    annotation_file = data.get('annotation_file', None)

    if os.path.exists(f"runs/{run_id}"):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        brownotate_version = detect_brownotate_version(repo_root)

        if annotation_file and os.path.exists(annotation_file):
            shutil.copy(annotation_file, f"runs/{run_id}/{os.path.basename(annotation_file)}")
            progress = "Annotation run completed successfully"
        else:
            progress = "Annotation stopped: insufficient genes identified during protein evidence comparison"

        find_run_results = find_one('runs', {'parameters.id': int(run_id)})
        if not find_run_results['data']:
            return jsonify({'status': 'error', 'message': 'Run not found'}), 404
        
        if 'progress' in find_run_results['data']:
            progress_list = find_run_results['data']['progress']
            progress = progress_list + [progress]
        else:
            progress = None

        # Remove temporary Scipio/split artifacts before archiving.
        annotation_dir = os.path.join('runs', str(run_id), 'annotation')
        if os.path.isdir(annotation_dir):
            for file in os.listdir(annotation_dir):
                file_path = os.path.join(annotation_dir, file)
                if file.startswith('scipio_work_dir_') and os.path.isdir(file_path):
                    shutil.rmtree(file_path, ignore_errors=True)
                elif file.endswith('_simplified.fasta') and os.path.isfile(file_path):
                    os.remove(file_path)
                elif file.startswith('file_') and file.endswith('.fasta') and os.path.isfile(file_path):
                    os.remove(file_path)
                
        output_run_path = move_wd_to_output_runs_folder(str(run_id))

        run_data_for_report = find_run_results.get('data') if isinstance(find_run_results, dict) else None
        is_functional_run = bool((run_data_for_report or {}).get('parameters', {}).get('type') == 'functional')

        if is_functional_run:
            progress = "Brownaming run completed successfully"

        if output_run_path and run_data_for_report:
            write_parameters_report(run_data_for_report, output_run_path)

            # For Brownaming-only runs, include parameters.txt in the downloadable brownaming zip.
            if is_functional_run:
                parameters_file = os.path.join(output_run_path, 'parameters.txt')
                brownaming_dir = os.path.join(output_run_path, 'brownaming')
                if os.path.isfile(parameters_file) and os.path.isdir(brownaming_dir):
                    shutil.move(parameters_file, os.path.join(brownaming_dir, 'parameters.txt'))

        completed = bool(annotation_file and os.path.exists(annotation_file))
        if is_functional_run and output_run_path:
            brownaming_dir = os.path.join(output_run_path, 'brownaming')
            completed = bool(
                os.path.isdir(brownaming_dir)
                and any(
                    os.path.isfile(os.path.join(brownaming_dir, item))
                    for item in os.listdir(brownaming_dir)
                )
            )

        if progress:
            if completed:
                update_one('runs', {"parameters.id": int(run_id)}, {"$set": {"status": "completed", "progress": progress, "results_path": output_run_path, "resumeData.brownotate_version": brownotate_version}})
            else:
                update_one('runs', {"parameters.id": int(run_id)}, {"$set": {"status": "incomplete", "progress": progress, "results_path": output_run_path, "resumeData.brownotate_version": brownotate_version}})
        else:
            update_one('runs', {"parameters.id": int(run_id)}, {"$set": {"status": "completed" if completed else "incomplete", "results_path": output_run_path, "resumeData.brownotate_version": brownotate_version}})
    else:
        return jsonify({'status': 'error', 'message': f'Run directory for run_id {run_id} does not exist'}), 400

    return jsonify({'status': 'success', 'message': 'Annotation status updated successfully'}), 200
