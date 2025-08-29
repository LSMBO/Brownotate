import os
from flask import Blueprint, request, jsonify
from utils import load_config
from flask_app.file_ops import create_download_folder
import subprocess

download_uniprot_bp = Blueprint('download_uniprot_bp', __name__)

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@download_uniprot_bp.route('/download_uniprot', methods=['POST'])
def download_uniprot():
    url = request.json.get('url')
    output_name = request.json.get('output_name')
    
    try:
        download_folder = create_download_folder() # f"user_download/{dd-mm-yyyy}"
        server_filename = os.path.join(config['BROWNOTATE_PATH'], download_folder, output_name) # /home/ubuntu/br/bin/Brownotate/{download_folder}/{output_name}
        
        if os.path.exists(server_filename):
            return jsonify({'status': 'success', 'path': server_filename}), 200
        
        print(f"wget -O {server_filename} {url}")
        subprocess.run(['wget', '-O', server_filename, url], check=True, env=env)
        return jsonify({'status': 'success', 'path': server_filename}), 200

    except Exception as e:
        if os.path.exists(server_filename):
            os.remove(server_filename)
        return jsonify({'status': 'error', 'message': str(e)}), 500 