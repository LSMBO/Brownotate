import os
from flask import Blueprint, request, jsonify

get_files_bp = Blueprint('get_files_bp', __name__)

@get_files_bp.route('/get_files', methods=['POST'])
def get_files():
    data = request.json
    path = data.get('path')
    extension = data.get('extension')
    if not path or not extension:
        return jsonify({'status': 'error', 'message': 'Missing file parameter'}), 400
    
    if extension == ".fasta":
        extensions = extensions + [".fna", ".faa", ".fa", ".fna.gz", ".faa.gz", ".fa.gz", ".fasta.gz"]
    matching_files = []
    try:
        if os.path.isdir(path):
            files = os.listdir(path)
            for file in files:
                for ext in extensions:
                    if file.endswith(ext):
                        matching_files.append(f"{path}/{file}")
            return jsonify({'results' : matching_files})
        else:
            return "Invalid path", 400
    except Exception as e:
        return str(e), 500
