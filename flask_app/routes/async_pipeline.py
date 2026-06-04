import threading

from flask import Blueprint, current_app, jsonify, request

from flask_app.step_status import (
    get_step_status,
    mark_step_error,
    mark_step_running,
    mark_step_success,
)
from flask_app.orchestration_engine import AnnotationOrchestrator
from flask_app.database import find_one, update_one
from bson.int64 import Int64

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


# =========================================================================
# NEW UNIFIED ORCHESTRATION ROUTE
# =========================================================================
# This is the single main entry point for annotation runs.
# Client sends all parameters once, server orchestrates everything.

def _background_orchestrate(app, run_id, parameters, cpus):
    """Run the orchestrator in background thread."""
    try:
        with app.app_context():
            orchestrator = AnnotationOrchestrator(run_id, parameters, cpus, None)
            orchestrator.orchestrate()
    except Exception as e:
        print(f"[ORCHESTRATOR] Error in background orchestration: {e}")
        try:
            with app.app_context():
                for query in [
                    {'parameters.id': Int64(run_id)},
                    {'parameters.id': int(run_id)},
                    {'parameters.id': str(run_id)},
                ]:
                    update_one('runs', query, {'$set': {'status': 'failed', 'error': str(e)}})
        except:
            pass


@async_pipeline_bp.route('/run_annotation_orchestrated', methods=['POST'])
def run_annotation_orchestrated():
    """
    Main orchestration route.
    
    Accepts full parameters and launches the entire annotation pipeline.
    The server orchestrates all steps; client only polls for progress.
    
    Request payload:
    {
        "run_id": <int>,
        "user": "<username>",
        "parameters": { ... full parameters object ... },
        "cpus": <int>
    }
    
    Returns:
    {
        "status": "started",
        "run_id": <int>,
        "message": "Annotation pipeline orchestration started"
    }
    """
    payload = request.json or {}
    
    run_id = payload.get('run_id')
    if run_id is None:
        return jsonify({
            'status': 'error',
            'message': 'run_id is required'
        }), 400
    
    run_id = int(run_id)
    parameters = payload.get('parameters', {})
    cpus = payload.get('cpus', 4)
    user = payload.get('user', 'unknown')
    
    if not parameters:
        return jsonify({
            'status': 'error',
            'message': 'parameters are required'
        }), 400
    
    # Verify run exists and is in correct state
    try:
        for query in [
            {'parameters.id': Int64(run_id)},
            {'parameters.id': int(run_id)},
            {'parameters.id': str(run_id)},
        ]:
            run = find_one('runs', query)
            run_data = run.get('data') if isinstance(run, dict) else None
            if run.get('status') == 'success' and run_data:
                current_progress = run_data.get('progress', [])
                if isinstance(current_progress, list):
                    progress_list = list(current_progress)
                elif current_progress:
                    progress_list = [current_progress]
                else:
                    progress_list = []

                if not progress_list or progress_list[-1] != 'Starting orchestration...':
                    progress_list.append('Starting orchestration...')

                # Keep previously completed client-side setup/evidence steps visible in the run history.
                update_one('runs', query, {'$set': {'status': 'running', 'progress': progress_list, 'error': ''}})
                break
        else:
            return jsonify({
                'status': 'error',
                'message': f'Run {run_id} not found'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }), 500
    
    # Launch orchestrator in background thread
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_background_orchestrate,
        args=(app, run_id, parameters, cpus)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'started',
        'run_id': run_id,
        'message': 'Annotation pipeline orchestration started'
    }), 200
