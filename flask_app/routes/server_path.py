import os
from flask import Blueprint, request, jsonify

server_path_bp = Blueprint('server_path_bp', __name__)

@server_path_bp.route('/server_path', methods=['POST'])
def server_path():
    try:
        data = request.json
        path = data.get('path')
        extension = data.get('extension')
        
        if not os.path.exists(path):
            return jsonify({"error": "Path not found"}), 404
        
        if extension == ".fasta" or extension == ".fa" or extension == ".fna" or extension == ".faa":
            extensions = (".fasta", ".fa", ".fna", ".faa")
        else:
            extensions = extension
        matching_files = []
        for file in os.listdir(path):
            if file.endswith(extensions):
                matching_files.append(os.path.join(path, file))
        return jsonify({"results": matching_files}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
