from flask import Blueprint, request, send_file

get_image_bp = Blueprint('get_image_bp', __name__)

@get_image_bp.route('/get_image/<path:filename>', methods=['GET'])
def get_image(filename):
    filepath =  f"../{filename}"
    return send_file(filepath, mimetype='image/png')