import os
from flask import Blueprint, request, jsonify
from utils import load_config
from flask_app.file_ops import create_download_folder
import subprocess
from datetime import datetime
from timer import timer

merge_fasta_files_bp = Blueprint('merge_fasta_files_bp', __name__)

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@merge_fasta_files_bp.route('/merge_fasta_files', methods=['POST'])
def merge_fasta_files():
    start_time = timer.start()
    files = request.json.get('files')

    try:
        download_folder = create_download_folder()
        timestamp = datetime.now().strftime('%H%M%S')
        server_filename = os.path.join(config['BROWNOTATE_PATH'], download_folder, f'Merged_Protein_Files_{timestamp}.fasta')
        raw_merged_filename = os.path.join(config['BROWNOTATE_PATH'], download_folder, f'Merged_Protein_Files_raw_{timestamp}.fasta')
        
        with open(raw_merged_filename, 'w') as outfile:
            for fasta_file in files:
                with open(fasta_file, 'r') as infile:
                    outfile.write(infile.read())

        cdhit_command = [
            'cd-hit',
            '-i', raw_merged_filename,
            '-o', server_filename,
            '-c', '1',
            '-G', '0',
            '-aL', '1'
        ]
        print(' '.join(cdhit_command))
        subprocess.run(cdhit_command, check=True, env=env)
        return jsonify({'status': 'success', 'path': server_filename, 'timer': timer.stop(start_time)}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500 