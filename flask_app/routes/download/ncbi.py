import os
from flask import Blueprint, request, jsonify
from utils import load_config
from flask_app.file_ops import create_download_folder
import shutil
import subprocess

download_ncbi_bp = Blueprint('download_ncbi_bp', __name__)

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@download_ncbi_bp.route('/download_ncbi', methods=['POST'])
def download_ncbi():
    download_command = request.json.get('download_command')

    try:
        download_folder = create_download_folder() # f"user_download/{dd-mm-yyyy}"
        zip_path = os.path.join(download_folder, download_command[6]) # f"{download_folder}/{accession}_annotation.zip"
        print(download_command)
        print(f"zip_path: {zip_path}")
        unzip_dir = os.path.splitext(zip_path)[0] # f"{download_folder}/{accession}_annotation"
        server_filename = os.path.join(config['BROWNOTATE_PATH'], unzip_dir + ".fasta") # /home/ubuntu/br/bin/Brownotate/{download_folder}/{accession}_annotation.fasta
        download_command[6] = zip_path # f"{download_folder}/{accession}_annotation.zip"
        
        if os.path.exists(server_filename):
            return jsonify({'status': 'success', 'path': server_filename}), 200
        print(download_command)
        result = subprocess.run(
            download_command, capture_output=True, text=True, check=True, env=env
        )
        
        shutil.unpack_archive(zip_path, unzip_dir)
        
        accession = download_command[4]
        archive_last_dir = os.path.join(unzip_dir, 'ncbi_dataset', 'data', accession) # f"{download_folder}/{accession}_annotation/ncbi_dataset/data/{accession}"
        result_file_path = next(iter(os.listdir(archive_last_dir))) # f"{assembly/annotation.fasta}"
        result_file_path = os.path.join(archive_last_dir, result_file_path) # f"{download_folder}/{accession}_annotation/ncbi_dataset/data/{accession}/{assembly/annotation.fasta}"
        
        shutil.move(result_file_path, server_filename) # Move f"{download_folder}/{accession}_annotation/ncbi_dataset/data/{accession}/{assembly/annotation.fasta}" to f"{download_folder}/{accession}_annotation.fasta"
        shutil.rmtree(unzip_dir) # Remove f"{download_folder}/{accession}_annotation"
        os.remove(f"{unzip_dir}.zip") # Remove f"{download_folder}/{accession}_annotation.zip"
        print(server_filename)
        return jsonify({'status': 'success', 'path': server_filename}), 200

    except Exception as e:
        if os.path.exists(unzip_dir):
            shutil.rmtree(unzip_dir)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(server_filename):
            os.remove(server_filename)
        return jsonify({'status': 'error', 'message': str(e)}), 500