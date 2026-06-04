from flask import Blueprint, request, jsonify

from flask_app.database import find_one, update_one

get_error_message_bp = Blueprint('get_error_message_bp', __name__)


def _is_meaningful(value):
    if value is None:
        return False
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned != '' and cleaned.lower() not in {'failed', 'pipeline failed', 'command failed'}
    if isinstance(value, dict):
        return any(_is_meaningful(v) for v in value.values())
    return True


def _extract_primary_error(run_data):
    run_id = run_data.get('run_id') or run_data.get('parameters', {}).get('id')
    existing_error = run_data.get('error')

    if isinstance(existing_error, dict):
        message = existing_error.get('message') or existing_error.get('error') or existing_error.get('detail')
        if _is_meaningful(message):
            return {
                'run_id': run_id,
                'step': existing_error.get('step') or 'pipeline',
                'message': str(message),
                'source': 'error'
            }

    if isinstance(existing_error, str) and _is_meaningful(existing_error):
        return {
            'run_id': run_id,
            'step': 'pipeline',
            'message': existing_error.strip(),
            'source': 'error'
        }

    resume_data = run_data.get('resumeData', {}) or {}

    preferred_keys = [
        ('busco_assembly_error', 'busco_assembly'),
        ('busco_annotation_error', 'busco_annotation'),
        ('brownaming_error', 'brownaming'),
        ('rnabloom_error', 'rnabloom'),
        ('trinity_error', 'trinity'),
        ('transdecoder_error', 'transdecoder'),
        ('augustus_error', 'augustus'),
        ('scipio_error', 'scipio'),
        ('model_error', 'model'),
        ('optimize_model_error', 'optimize_model'),
        ('prokka_error', 'prokka'),
        ('megahit_error', 'megahit'),
        ('canu_error', 'canu'),
        ('fastp_error', 'fastp'),
        ('remove_phix_error', 'remove_phix'),
    ]

    for key, step in preferred_keys:
        value = resume_data.get(key)
        if _is_meaningful(value):
            return {
                'run_id': run_id,
                'step': step,
                'message': str(value).strip(),
                'source': 'resumeData'
            }

    for key, value in resume_data.items():
        if key.endswith('_error') and _is_meaningful(value):
            return {
                'run_id': run_id,
                'step': key[:-6],
                'message': str(value).strip(),
                'source': 'resumeData'
            }

    for key, value in resume_data.items():
        if key.endswith('_detail') and _is_meaningful(value):
            return {
                'run_id': run_id,
                'step': key[:-7],
                'message': str(value).strip(),
                'source': 'resumeData'
            }

    return {
        'run_id': run_id,
        'step': 'pipeline',
        'message': 'Pipeline failed. No detailed error message was saved by this run.',
        'source': 'fallback'
    }


@get_error_message_bp.route('/get_error_message', methods=['POST'])
def get_error_message():
    run_id = request.json.get('run_id')
    if run_id is None:
        return jsonify({'status': 'error', 'message': 'Missing run_id'}), 400

    run = find_one('runs', {'parameters.id': int(run_id)})
    if run['status'] != 'success' or not run.get('data'):
        return jsonify({'status': 'error', 'message': 'Run not found'}), 404

    run_data = run['data']
    error_payload = _extract_primary_error(run_data)

    # Keep a normalized error object in DB so the frontend can display useful details consistently.
    if not isinstance(run_data.get('error'), dict) or not _is_meaningful(run_data.get('error')):
        update_one(
            'runs',
            {'parameters.id': int(run_id)},
            {
                '$set': {
                    'error': {
                        'message': error_payload['message'],
                        'step': error_payload['step'],
                        'source': error_payload['source']
                    }
                }
            }
        )

    return jsonify({'status': 'success', 'data': error_payload}), 200
