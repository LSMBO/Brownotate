import os
from flask import Blueprint, request, jsonify, send_file
from flask_app.file_ops import download_zip
from utils import load_config

download_server_bp = Blueprint('download_server_bp', __name__)
config = load_config()

@download_server_bp.route('/download_server', methods=['POST'])
def download_server():
    try:
        data = request.json
        path = data.get('file')
        
        if not os.path.exists(path):
            return jsonify({"error": "File not found"}), 404
        
        path = os.path.join(config['BROWNOTATE_PATH'], path)
        
        if os.path.isdir(path):
            return download_zip(path)
        
        elif os.path.isfile(path):
            return send_file(path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


