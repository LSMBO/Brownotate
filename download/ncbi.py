import os
from flask import Blueprint, request, jsonify
from flask_app.utils import load_config
from flask_app.file_ops import create_download_folder
import shutil
import subprocess
import glob
import time

download_ncbi_bp = Blueprint('download_ncbi_bp', __name__)

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


def _cleanup_download_artifacts(zip_path, unzip_dir, server_filename):
    if os.path.exists(unzip_dir or ''):
        shutil.rmtree(unzip_dir)
    if os.path.exists(zip_path or ''):
        os.remove(zip_path)
    if os.path.exists(server_filename or ''):
        os.remove(server_filename)


def _run_download_command_with_retries(download_command, env, zip_path, unzip_dir, server_filename, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(download_command, capture_output=True, text=True, check=True, env=env)
            return
        except subprocess.CalledProcessError as e:
            last_error = e
            _cleanup_download_artifacts(zip_path, unzip_dir, server_filename)
            if attempt < attempts:
                time.sleep(min(10, 2 * attempt))

    if last_error is not None:
        raise last_error

@download_ncbi_bp.route('/download_ncbi', methods=['POST'])
def download_ncbi():
    download_command = request.json.get('download_command')
    zip_path = None
    unzip_dir = None
    server_filename = None

    try:
        if not isinstance(download_command, list) or len(download_command) < 5:
            return jsonify({'status': 'error', 'message': 'Invalid download_command format'}), 400

        try:
            accession = download_command[download_command.index('accession') + 1]
        except (ValueError, IndexError):
            accession = download_command[4]

        filename = None
        try:
            filename = download_command[download_command.index('--filename') + 1]
        except (ValueError, IndexError):
            filename = None

        if not filename:
            filename = f"{accession}_annotation.zip"
            download_command += ['--filename', filename]

        include_value = None
        try:
            include_value = str(download_command[download_command.index('--include') + 1]).lower()
        except (ValueError, IndexError):
            include_value = None

        is_genome_download = include_value == 'genome'

        download_folder = create_download_folder() # f"user_download/{dd-mm-yyyy}"
        zip_path = os.path.join(download_folder, filename) # f"{download_folder}/{accession}_annotation.zip"
        unzip_dir = os.path.splitext(zip_path)[0] # f"{download_folder}/{accession}_annotation"
        output_ext = ".fna" if is_genome_download else ".fasta"
        output_suffix = "_assembly" if is_genome_download else "_annotation"
        server_filename = os.path.join(config['BROWNOTATE_PATH'], os.path.join(download_folder, f"{accession}{output_suffix}{output_ext}"))
        os.makedirs(os.path.dirname(server_filename), exist_ok=True)

        filename_flag_index = download_command.index('--filename')
        if filename_flag_index + 1 >= len(download_command):
            return jsonify({'status': 'error', 'message': 'Invalid download_command: --filename has no value'}), 400
        download_command[filename_flag_index + 1] = zip_path # f"{download_folder}/{accession}_annotation.zip"
        
        if os.path.exists(server_filename) and os.path.getsize(server_filename) > 0:
            return jsonify({'status': 'success', 'path': server_filename}), 200

        _run_download_command_with_retries(
            download_command,
            env,
            zip_path,
            unzip_dir,
            server_filename,
        )
        
        shutil.unpack_archive(zip_path, unzip_dir)

        archive_last_dir = os.path.join(unzip_dir, 'ncbi_dataset', 'data', accession) # f"{download_folder}/{accession}_annotation/ncbi_dataset/data/{accession}"

        candidate_files = []
        primary_exts = ['*.fna', '*.fasta', '*.fa'] if is_genome_download else ['*.faa', '*.fasta', '*.fa']
        fallback_exts = ['*.fasta', '*.fa', '*.fna', '*.faa']

        def collect_candidates(root_dir, exts):
            if not os.path.isdir(root_dir):
                return []
            found = []
            for ext in exts:
                found.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
            return found

        if os.path.isdir(archive_last_dir):
            candidate_files.extend(collect_candidates(archive_last_dir, primary_exts))

        # Fallback if NCBI package layout changes and accession folder is not present.
        if not candidate_files:
            data_root = os.path.join(unzip_dir, 'ncbi_dataset', 'data')
            candidate_files.extend(collect_candidates(data_root, primary_exts))

        if not candidate_files:
            data_root = os.path.join(unzip_dir, 'ncbi_dataset', 'data')
            candidate_files.extend(collect_candidates(data_root, fallback_exts))

        if not candidate_files:
            expected = 'genome FASTA (.fna)' if is_genome_download else 'protein FASTA (.faa/.fasta/.fa)'
            raise FileNotFoundError(f"No {expected} file found in extracted archive for accession {accession}")

        result_file_path = candidate_files[0]
        
        shutil.move(result_file_path, server_filename) # Move f"{download_folder}/{accession}_annotation/ncbi_dataset/data/{accession}/{assembly/annotation.fasta}" to f"{download_folder}/{accession}_annotation.fasta"
        shutil.rmtree(unzip_dir) # Remove f"{download_folder}/{accession}_annotation"
        os.remove(f"{unzip_dir}.zip") # Remove f"{download_folder}/{accession}_annotation.zip"
        return jsonify({'status': 'success', 'path': server_filename}), 200

    except subprocess.CalledProcessError as e:
        _cleanup_download_artifacts(zip_path, unzip_dir, server_filename)
        return jsonify({'status': 'error', 'message': e.stderr or e.stdout or str(e)}), 500

    except Exception as e:
        _cleanup_download_artifacts(zip_path, unzip_dir, server_filename)
        return jsonify({'status': 'error', 'message': str(e)}), 500