import os
from flask import Blueprint, request, jsonify, send_file
from flask_app.file_ops import download_zip
from flask_app.utils import load_config

download_server_bp = Blueprint('download_server_bp', __name__)
config = load_config()

@download_server_bp.route('/download_server', methods=['POST'])
def download_server():
    try:
        data = request.json
        requested_path = data.get('file')
        if not requested_path:
            return jsonify({"error": "Missing file path"}), 400

        if os.path.isabs(requested_path):
            path = requested_path
        else:
            path = os.path.join(config['BROWNOTATE_PATH'], requested_path)

        if not os.path.exists(path):
            return jsonify({"error": "File not found"}), 404

        if os.path.isdir(path):
            return download_zip(path)
        
        elif os.path.isfile(path):
            return send_file(path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


