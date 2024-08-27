import os
from flask import Blueprint, request, jsonify, send_file
from flask_app.file_ops import download_zip

download_file_server_bp = Blueprint('download_file_server_bp', __name__)

@download_file_server_bp.route('/download_file_server', methods=['POST'])
def download_file_server():
    try:
        data = request.json
        path = data.get('file')

        if not os.path.exists(path):
            return jsonify({"error": "File not found"}), 404

        if os.path.isdir(path):
            return download_zip(path)
        elif os.path.isfile(path):
            return send_file(path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

