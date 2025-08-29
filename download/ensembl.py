import os
from flask import Blueprint, request, jsonify, send_file
import ftplib
from utils import load_config
from flask_app.file_ops import create_download_folder
import gzip
import shutil


download_ensembl_ftp_bp = Blueprint('download_ensembl_ftp_bp', __name__)
config = load_config()


@download_ensembl_ftp_bp.route('/download_ensembl_ftp', methods=['POST'])
def download_ensembl_ftp():
    path = request.json.get('file')
    output_name = request.json.get('output_name')
    
    if not path:
        return jsonify({'status': 'error', 'message': 'Missing file parameter'}), 400

    try:
        download_folder = create_download_folder() # f"user_download/{dd-mm-yyyy}"
        server_filename = os.path.join(config['BROWNOTATE_PATH'], download_folder, f"{output_name}.gz") # /home/ubuntu/br/bin/Brownotate/{download_folder}/{output_name}.gz
        decompressed_server_file = server_filename.rstrip('.gz') # /home/ubuntu/br/bin/Brownotate/{download_folder}/{output_name}
        
        if os.path.exists(decompressed_server_file):
            return jsonify({'status': 'success', 'message': 'File downloaded successfully', 'path': decompressed_server_file}), 200
        
        ftp = ftplib.FTP("ftp.ensembl.org")
        ftp.login()
        relative_path = path.split('ftp.ensembl.org')[1]
        directory = "/".join(relative_path.split("/")[:-1])
        filename = relative_path.split("/")[-1]
        ftp.cwd(directory)
        
        with open(server_filename, 'wb') as f:
            ftp.retrbinary(f'RETR {filename}', f.write)
        ftp.quit()

        with gzip.open(server_filename, 'rb') as f_in:
            with open(decompressed_server_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(server_filename)
        
        return jsonify({'status': 'success', 'message': 'File downloaded successfully', 'path': decompressed_server_file}), 200
    
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'File or directory not found on FTP server'}), 404
    
    except Exception as e:
        if os.path.exists(server_filename):
            os.remove(server_filename)
        if os.path.exists(decompressed_server_file):
            os.remove(decompressed_server_file)
        return jsonify({'status': 'error', 'message': str(e)}), 500