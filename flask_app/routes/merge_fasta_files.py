import os
import shutil
from flask import Blueprint, request, jsonify
from ..utils import load_config
from flask_app.commands import run_command
from flask_app.file_ops import create_download_folder
from datetime import datetime
from timer import timer

merge_fasta_files_bp = Blueprint('merge_fasta_files_bp', __name__)

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@merge_fasta_files_bp.route('/merge_fasta_files', methods=['POST'])
def merge_fasta_files():
    start_time = timer.start()
    files = request.json.get('files') or []
    run_id = request.json.get('run_id', None)
    merge_scope = request.json.get('merge_scope', 'run')
    try:
        valid_files = [
            fasta_file for fasta_file in files
            if isinstance(fasta_file, str)
            and fasta_file.strip()
            and fasta_file.strip().lower() != 'none'
            and os.path.exists(fasta_file)
            and os.path.getsize(fasta_file) > 0
        ]

        if not valid_files:
            return jsonify({'status': 'error', 'message': 'No valid FASTA evidence files were provided.', 'timer': timer.stop(start_time)}), 400

        if merge_scope == 'run':
            if not run_id:
                return jsonify({'status': 'error', 'message': 'run_id is required for run-scoped evidence merge.', 'timer': timer.stop(start_time)}), 400
            evidence_dir = os.path.join(config['BROWNOTATE_PATH'], 'runs', str(run_id), 'evidence')
        else:
            download_dir = create_download_folder()
            evidence_dir = os.path.join(config['BROWNOTATE_PATH'], download_dir, 'evidence_merge')

        os.makedirs(evidence_dir, exist_ok=True)

        # Keep an immutable copy of original evidence files inside the run folder.
        copied_source_files = []
        seen_basenames = {}
        for source in valid_files:
            source_name = os.path.basename(source)
            count = seen_basenames.get(source_name, 0)
            seen_basenames[source_name] = count + 1
            if count == 0:
                target_name = source_name
            else:
                stem, ext = os.path.splitext(source_name)
                target_name = f"{stem}_{count + 1}{ext}"

            target = os.path.join(evidence_dir, target_name)
            if os.path.abspath(source) != os.path.abspath(target):
                shutil.copy2(source, target)
            copied_source_files.append(target)

        if len(valid_files) == 1:
            target = copied_source_files[0]
            return jsonify({
                'status': 'success',
                'path': target,
                'source_files': valid_files,
                'copied_source_files': copied_source_files,
                'timer': timer.stop(start_time)
            }), 200

        timestamp = datetime.now().strftime('%H%M%S')
        server_filename = os.path.join(evidence_dir, f'Merged_Protein_Files_{timestamp}.fasta')
        raw_merged_filename = os.path.join(evidence_dir, f'Merged_Protein_Files_raw_{timestamp}.fasta')
        
        with open(raw_merged_filename, 'w') as outfile:
            for fasta_file in valid_files:
                with open(fasta_file, 'r') as infile:
                    outfile.write(infile.read())

        if not os.path.exists(raw_merged_filename) or os.path.getsize(raw_merged_filename) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Merged raw evidence file is missing or empty.',
                'timer': timer.stop(start_time)
            }), 500

        command = f"cd-hit -i {raw_merged_filename} -o {server_filename} -c 1 -G 0 -aL 1"
        stdout, stderr, returncode = run_command(command, run_id, env=env)
        if returncode != 0 or not os.path.exists(server_filename) or os.path.getsize(server_filename) == 0:
            print(f"cd-hit failed for evidence merge, using raw merged file instead. stderr: {stderr}")
            return jsonify({
                'status': 'success',
                'path': raw_merged_filename,
                'source_files': valid_files,
                'copied_source_files': copied_source_files,
                'warning': 'cd-hit failed, using raw merged file instead.',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 200

        return jsonify({
            'status': 'success',
            'path': server_filename,
            'source_files': valid_files,
            'copied_source_files': copied_source_files,
            'timer': timer.stop(start_time)
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'timer': timer.stop(start_time)}), 500 