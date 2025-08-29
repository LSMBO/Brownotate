from flask import Blueprint, request, jsonify
from flask_app.database import update_one

update_run_bp = Blueprint('update_run_bp', __name__)

def clean_key(key: str) -> str:
    return key.replace('.', '')

@update_run_bp.route('/update_run', methods=['POST'])
def update_run():
    data = request.json
    run_id = data.get('run_id')
    field = data.get('field')
    value = data.get('value')    
    if isinstance(value, dict):
        cleaned_dict = {clean_key(k): v for k, v in value.items()}
        update_result = update_one('runs', {"parameters.id": int(run_id)}, {"$set": {f"{field}.{k}": v for k, v in cleaned_dict.items()}})
    else:
        update_result = update_one('runs', {"parameters.id": int(run_id)}, {"$set": {field: value}})

    return jsonify({'status': 'success', 'message': 'Run status updated successfully'}), 200
