import os
from flask import Blueprint, request, jsonify, send_file
from flask_app.file_ops import download_zip

download_file_bp = Blueprint('download_file_bp', __name__)

@download_file_bp.route('/download_file', methods=['POST'])
def download_file():
    data = request.form
    path = data.get('file')
    if not path:
        return jsonify({'status': 'error', 'message': 'Missing file parameter'}), 400
    
    if not os.path.exists(path):
        return jsonify({'status': 'error', 'message': 'File or directory not found'}), 404
    try:
        if os.path.isdir(path):
            return download_zip(path)
        elif os.path.isfile(path):
            return send_file(path, as_attachment=True)
        else:
            return jsonify({'status': 'error', 'message': 'Path is not a file or directory'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500