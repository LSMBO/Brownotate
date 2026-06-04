import os
from flask import Blueprint, send_file, jsonify
from flask_app.utils import load_config

get_image_bp = Blueprint('get_image_bp', __name__)
config = load_config()

@get_image_bp.route('/get_image/<path:filename>', methods=['GET'])
def get_image(filename):
    candidates = []

    # Relative path used in most records (e.g. user_download/... or output_runs/...)
    candidates.append(os.path.normpath(os.path.join(config['BROWNOTATE_PATH'], filename)))

    # Legacy fallback from prior behavior
    candidates.append(os.path.normpath(os.path.join('..', filename)))

    # Absolute path support (frontend can pass paths rooted at /home/...)
    if filename.startswith('/'):
        candidates.append(filename)
    else:
        candidates.append('/' + filename)

    filepath = next((path for path in candidates if os.path.exists(path)), None)
    if not filepath:
        return jsonify({'status': 'error', 'message': f'Image not found: {filename}'}), 404

    return send_file(filepath)