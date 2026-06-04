from flask import Blueprint, jsonify
from flask_app.database import runs_collection

MAX_CONCURRENT_ANNOTATIONS = 2
ANNOTATION_CPUS = 12

get_cpus_bp = Blueprint('get_cpus_bp', __name__)

@get_cpus_bp.route('/get_cpus', methods=['GET'])
def get_cpus():
    running_count = runs_collection.count_documents({'status': 'running'})
    can_start = running_count < MAX_CONCURRENT_ANNOTATIONS
    return jsonify({
        'status': 'success',
        'can_start': can_start,
        'running_count': running_count,
        'cpus': ANNOTATION_CPUS
    }), 200
