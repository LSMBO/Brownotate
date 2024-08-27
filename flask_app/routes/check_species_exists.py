from flask import Blueprint, request, jsonify
from flask_app.commands import build_check_species_exists_command, run_command
import uuid

check_species_exists_bp = Blueprint('check_species_exists_bp', __name__)

@check_species_exists_bp.route('/check_species_exists', methods=['POST'])
def check_species_exists():
    species = request.json.get('species')
    if not species:
        return jsonify({'status': 'error', 'message': 'Missing species parameter'}), 400

    run_id = str(uuid.uuid4())
    command = build_check_species_exists_command(species)
    stdout, stderr = run_command(command, run_id)
    if stderr:
        return jsonify({'status': 'error', 'message': stderr}), 500

    scientific_name = stdout.split(';')[0]
    taxID = stdout.split(';')[1][:-1]
    return jsonify({'status': 'success', 'results': {'scientific_name': scientific_name, 'taxID': taxID}})
