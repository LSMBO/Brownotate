import threading

from flask import Blueprint, current_app, jsonify, request

from flask_app.step_status import (
    get_step_status,
    mark_step_error,
    mark_step_running,
    mark_step_success,
)

async_pipeline_bp = Blueprint('async_pipeline_bp', __name__)


def _run_id_from_payload(payload):
    if payload.get('run_id') is not None:
        return int(payload.get('run_id'))
    parameters = payload.get('parameters', {})
    if parameters.get('id') is not None:
        return int(parameters.get('id'))
    return None


def _background_execute(app, run_id, step_name, sync_route, payload):
    # Run the existing synchronous route in a background thread and persist final step state.
    try:
        with app.app_context():
            with app.test_client() as client:
                response = client.post(sync_route, json=payload)
                body = response.get_json(silent=True) or {}

        if response.status_code == 200 and body.get('status') == 'success':
            result_payload = body.get('data') if body.get('data') is not None else body
            mark_step_success(run_id, step_name, result=result_payload, timer_value=body.get('timer'), payload=payload)
        else:
            message = body.get('message') if isinstance(body, dict) else None
            if not message:
                message = response.get_data(as_text=True) or f'{step_name} failed'
            mark_step_error(run_id, step_name, message, payload=payload)
    except Exception as exc:
        mark_step_error(run_id, step_name, str(exc), payload=payload)


def _start_async(step_name, sync_route):
    payload = request.json or {}
    run_id = _run_id_from_payload(payload)
    if run_id is None:
        return jsonify({'status': 'error', 'message': 'run_id not found in request payload'}), 400

    # Single source of truth for polling is the DB step state.
    mark_step_running(run_id, step_name, payload=payload)

    app = current_app._get_current_object()
    thread = threading.Thread(target=_background_execute, args=(app, run_id, step_name, sync_route, payload))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started', 'message': f'{step_name} started in background', 'run_id': run_id}), 200


def _check_status(step_name):
    run_id = request.view_args.get('run_id')
    payload_like = {
        'flex': request.args.get('flex', 'false').lower() == 'true',
        'mode': request.args.get('mode', 'genome')
    }

    # Ultra-simple check: read current step state/result from MongoDB.
    status = get_step_status(run_id, step_name, payload=payload_like)
    if status.get('status') == 'error' and status.get('message') == 'Run not found':
        return jsonify(status), 404
    return jsonify(status), 200


@async_pipeline_bp.route('/run_fastp_async', methods=['POST'])
def run_fastp_async():
    return _start_async('fastp', '/run_fastp')


@async_pipeline_bp.route('/check_fastp_status/<int:run_id>', methods=['GET'])
def check_fastp_status(run_id):
    return _check_status('fastp')


@async_pipeline_bp.route('/run_remove_phix_async', methods=['POST'])
def run_remove_phix_async():
    return _start_async('remove_phix', '/run_remove_phix')


@async_pipeline_bp.route('/check_remove_phix_status/<int:run_id>', methods=['GET'])
def check_remove_phix_status(run_id):
    return _check_status('remove_phix')


@async_pipeline_bp.route('/run_megahit_async', methods=['POST'])
def run_megahit_async():
    return _start_async('megahit', '/run_megahit')


@async_pipeline_bp.route('/check_megahit_status/<int:run_id>', methods=['GET'])
def check_megahit_status(run_id):
    return _check_status('megahit')


@async_pipeline_bp.route('/run_prokka_async', methods=['POST'])
def run_prokka_async():
    return _start_async('prokka', '/run_prokka')


@async_pipeline_bp.route('/check_prokka_status/<int:run_id>', methods=['GET'])
def check_prokka_status(run_id):
    return _check_status('prokka')


@async_pipeline_bp.route('/run_augustus_async', methods=['POST'])
def run_augustus_async():
    return _start_async('augustus', '/run_augustus')


@async_pipeline_bp.route('/check_augustus_status/<int:run_id>', methods=['GET'])
def check_augustus_status(run_id):
    return _check_status('augustus')


@async_pipeline_bp.route('/run_scipio_async', methods=['POST'])
def run_scipio_async():
    return _start_async('scipio', '/run_scipio')


@async_pipeline_bp.route('/check_scipio_status/<int:run_id>', methods=['GET'])
def check_scipio_status(run_id):
    return _check_status('scipio')


@async_pipeline_bp.route('/run_model_async', methods=['POST'])
def run_model_async():
    return _start_async('model', '/run_model')


@async_pipeline_bp.route('/check_model_status/<int:run_id>', methods=['GET'])
def check_model_status(run_id):
    return _check_status('model')


@async_pipeline_bp.route('/run_optimize_model_async', methods=['POST'])
def run_optimize_model_async():
    return _start_async('optimize_model', '/run_optimize_model')


@async_pipeline_bp.route('/check_optimize_model_status/<int:run_id>', methods=['GET'])
def check_optimize_model_status(run_id):
    return _check_status('optimize_model')


@async_pipeline_bp.route('/run_brownaming_async', methods=['POST'])
def run_brownaming_async():
    return _start_async('brownaming', '/run_brownaming')


@async_pipeline_bp.route('/check_brownaming_status/<int:run_id>', methods=['GET'])
def check_brownaming_status(run_id):
    return _check_status('brownaming')


@async_pipeline_bp.route('/run_busco_async', methods=['POST'])
def run_busco_async():
    return _start_async('busco', '/run_busco')


@async_pipeline_bp.route('/check_busco_status/<int:run_id>', methods=['GET'])
def check_busco_status(run_id):
    return _check_status('busco')
