import time

from bson.int64 import Int64

from flask_app.database import find_one, update_one


def step_key(step_name, payload=None):
    payload = payload or {}
    if step_name == 'scipio':
        return 'scipio_flex' if payload.get('flex') else 'scipio'
    if step_name == 'busco':
        return 'busco_annotation' if payload.get('mode') == 'proteins' else 'busco_assembly'
    return step_name


def _queries(run_id):
    return [
        {'parameters.id': Int64(run_id)},
        {'parameters.id': int(run_id)},
        {'parameters.id': str(run_id)},
    ]


def _update_robust(run_id, update_data, retries=3):
    # Retry DB writes because run ids may be stored with mixed BSON types across historical runs.
    for attempt in range(retries):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))
        for query in _queries(run_id):
            result = update_one('runs', query, {'$set': update_data})
            if result['status'] == 'success':
                return True
    return False


def mark_step_running(run_id, step_name, payload=None):
    key = step_key(step_name, payload)
    update_data = {
        f'resumeData.{key}_step_state': 'running',
        f'resumeData.{key}_status': 'running',
        f'resumeData.{key}_error': '',
    }
    _update_robust(run_id, update_data)


def mark_step_success(run_id, step_name, result=None, timer_value=None, payload=None):
    key = step_key(step_name, payload)
    update_data = {
        f'resumeData.{key}_step_state': 'success',
        f'resumeData.{key}_status': 'completed',
        f'resumeData.{key}_error': '',
    }
    if result is not None:
        update_data[f'resumeData.{key}_result'] = result
    if timer_value is not None:
        # Use a safe key; Mongo field paths cannot contain dots from human labels.
        update_data[f'resumeData.{key}_timer'] = timer_value
    _update_robust(run_id, update_data)


def mark_step_error(run_id, step_name, error_message, payload=None):
    key = step_key(step_name, payload)
    update_data = {
        f'resumeData.{key}_step_state': 'error',
        f'resumeData.{key}_status': 'error',
        f'resumeData.{key}_error': str(error_message),
    }
    _update_robust(run_id, update_data)


def get_step_status(run_id, step_name, payload=None):
    key = step_key(step_name, payload)
    run_data = None
    for query in _queries(run_id):
        result = find_one('runs', query)
        if result['status'] == 'success' and result.get('data'):
            run_data = result['data']
            break

    if not run_data:
        return {'status': 'error', 'message': 'Run not found'}

    resume_data = run_data.get('resumeData', {})
    state = resume_data.get(f'{key}_step_state', 'not_started')
    # API compatibility: return "completed" to match the frontend polling contract.
    if state == 'success':
        response = {'status': 'completed'}
        response['result'] = resume_data.get(f'{key}_result')
        response['timer'] = resume_data.get(f'{key}_timer')
    elif state == 'error':
        response = {'status': 'error'}
        response['error'] = resume_data.get(f'{key}_error', f'{step_name} failed')
    elif state == 'running':
        response = {'status': 'running'}
    else:
        response = {'status': 'not_started'}

    return response
