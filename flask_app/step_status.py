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
    update_doc = update_data if any(str(key).startswith('$') for key in update_data.keys()) else {'$set': update_data}
    for attempt in range(retries):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))
        for query in _queries(run_id):
            result = update_one('runs', query, update_doc)
            if result['status'] == 'success':
                return True
    return False


def _safe_field(value):
    sanitized = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in str(value))
    return sanitized.strip('_') or 'unknown'


def mark_step_substatus(run_id, step_name, item_name, substep_name, status, detail=None, payload=None, result=None):
    key = step_key(step_name, payload)
    item_key = _safe_field(item_name)
    sub_key = _safe_field(substep_name)
    now = int(time.time())

    if status in ('pending', 'queued'):
        item_status = 'pending'
    elif status == 'error':
        item_status = 'error'
    elif status == 'completed' and sub_key in ('gff2gb', 'gff_to_genbank', 'chunk'):
        item_status = 'completed'
    else:
        item_status = 'running'

    update_data = {
        f'resumeData.{key}_chunks.{item_key}.status': item_status,
        f'resumeData.{key}_chunks.{item_key}.current_substep': sub_key,
        f'resumeData.{key}_chunks.{item_key}.updated_at': now,
        f'resumeData.{key}_chunks.{item_key}.{sub_key}.status': str(status),
        f'resumeData.{key}_chunks.{item_key}.{sub_key}.updated_at': now,
    }
    if detail is not None:
        update_data[f'resumeData.{key}_chunks.{item_key}.detail'] = str(detail)
        update_data[f'resumeData.{key}_chunks.{item_key}.{sub_key}.detail'] = str(detail)
    if result is not None:
        update_data[f'resumeData.{key}_chunks.{item_key}.{sub_key}.result'] = result
    _update_robust(run_id, update_data)


def mark_step_running(run_id, step_name, payload=None, detail=None):
    key = step_key(step_name, payload)
    now = int(time.time())
    update_data = {
        '$set': {
            f'resumeData.{key}_step_state': 'running',
            f'resumeData.{key}_status': 'running',
            f'resumeData.{key}_error': '',
            f'resumeData.{key}_detail': '' if detail is None else str(detail),
            f'resumeData.{key}_started_at': now,
        },
        '$unset': {
            f'resumeData.{key}_finished_at': '',
        }
    }
    _update_robust(run_id, update_data)


def mark_step_detail(run_id, step_name, detail, payload=None):
    key = step_key(step_name, payload)
    update_data = {
        f'resumeData.{key}_detail': str(detail),
        f'resumeData.{key}_status': 'running',
    }
    _update_robust(run_id, update_data)


def mark_step_success(run_id, step_name, result=None, timer_value=None, payload=None, detail=None):
    key = step_key(step_name, payload)
    update_data = {
        f'resumeData.{key}_step_state': 'success',
        f'resumeData.{key}_status': 'completed',
        f'resumeData.{key}_error': '',
        f'resumeData.{key}_finished_at': int(time.time()),
    }
    if detail is not None:
        update_data[f'resumeData.{key}_detail'] = str(detail)
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
        f'resumeData.{key}_detail': str(error_message),
        f'resumeData.{key}_finished_at': int(time.time()),
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
    detail = resume_data.get(f'{key}_detail', '')

    chunks = resume_data.get(f'{key}_chunks', {})

    if state == 'success':
        response = {'status': 'completed'}
        response['result'] = resume_data.get(f'{key}_result')
        response['timer'] = resume_data.get(f'{key}_timer')
        response['detail'] = detail
        response['chunks'] = chunks
    elif state == 'error':
        response = {'status': 'error'}
        response['error'] = resume_data.get(f'{key}_error', f'{step_name} failed')
        response['detail'] = detail
        response['chunks'] = chunks
    elif state == 'running':
        response = {'status': 'running'}
        response['detail'] = detail
        response['chunks'] = chunks
    else:
        response = {'status': 'not_started'}
        response['chunks'] = chunks

    return response
