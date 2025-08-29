from flask import Blueprint, request, jsonify
from flask_app.database import update_one
from flask_app.file_ops import move_wd_to_output_runs_folder
import os
import shutil

set_annotation_completed_bp = Blueprint('update_set_annotation_completed_bp', __name__)

@set_annotation_completed_bp.route('/set_annotation_completed', methods=['POST'])
def set_annotation_completed():
    data = request.json
    run_id = data.get('run_id')
    annotation_file = data.get('annotation_file')
    if os.path.exists(f"runs/{run_id}"):
        if os.path.exists(annotation_file):
            shutil.copy(annotation_file, f"runs/{run_id}/{os.path.basename(annotation_file)}")
            progress = "Annotation run completed successfully"
        else:
            progress = "Annotation stopped: insufficient genes identified during protein evidence comparison"
        
        # Clean up assembly duplicated files
        for file in os.listdir(f"runs/{run_id}"):
            if file.endswith('_simplified.fasta') or (file.startswith('file_') and file.endswith('.fasta')):
                os.remove(os.path.join(f"runs/{run_id}", file))
                
        output_run_path = move_wd_to_output_runs_folder(str(run_id))
        if progress == "Annotation run completed successfully":
            update_result = update_one('runs', {"parameters.id": int(run_id)}, {"$set": {"status": "completed", "progress": progress, "results_path": output_run_path}})
        else:
            update_result = update_one('runs', {"parameters.id": int(run_id)}, {"$set": {"status": "incompleted", "progress": progress, "results_path": output_run_path}})
    else:
        return jsonify({'status': 'error', 'message': f'Run directory for run_id {run_id} does not exist'}), 400
    return jsonify({'status': 'success', 'message': 'Annotation status updated successfully'}), 200
