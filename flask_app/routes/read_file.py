from flask import Blueprint, request, jsonify
import os

read_file_bp = Blueprint('read_file_bp', __name__)

@read_file_bp.route('/read_file', methods=['POST'])
def read_file():
    data = request.json
    path = data.get('path')
    file_type = data.get('file_type')

    if not path or not file_type:
        return jsonify({"error": "Missing path or file_type"}), 400

    # Vérifie si le fichier existe
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404

    try:
        with open(path, 'r') as file:
            file_content = file.read()

            if file_type == '.json':
                import json
                file_data = json.loads(file_content)
                return jsonify(file_data)
            else:
                return file_content

    except Exception as e:
        return jsonify({"error": str(e)}), 500
