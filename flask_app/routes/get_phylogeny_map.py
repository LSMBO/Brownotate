from flask import Blueprint, request, send_file
import os
import subprocess

get_phylogeny_map_bp = Blueprint('get_phylogeny_map_bp', __name__)

@get_phylogeny_map_bp.route('/get_phylogeny_map/<path:filename>', methods=['GET'])
def get_phylogeny_map(filename):
    filepath =  f"../{filename}"
    return send_file(filepath, mimetype='image/png')