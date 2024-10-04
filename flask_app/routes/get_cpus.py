import os
from flask import Blueprint, jsonify
from process_manager import get_cpus_used, get_max_cpu_usage_by_process


get_cpus_bp = Blueprint('get_cpus_bp', __name__)

@get_cpus_bp.route('/get_cpus', methods=['GET'])
def get_cpus():
    total_cpus = os.cpu_count()
    cpus_used_by_brownotate = get_cpus_used()
    cpus_used_by_gunicorn = get_max_cpu_usage_by_process('gunicorn')
    total_cpus_used = cpus_used_by_brownotate + cpus_used_by_gunicorn
    return jsonify({
        'status': 'success',
        'total_cpus': total_cpus,
        'total_cpus_used': total_cpus_used,
        'cpus_used_by_brownotate': cpus_used_by_brownotate,
        'cpus_used_by_gunicorn': cpus_used_by_gunicorn
    }), 200