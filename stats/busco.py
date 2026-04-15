import glob
import json
import os
import re
import shlex

from flask import Blueprint, jsonify, request

from flask_app.commands import run_command
from flask_app.step_status import mark_step_error, mark_step_running, mark_step_success
from flask_app.utils import load_config
from timer import timer

run_busco_bp = Blueprint('run_busco_bp', __name__)
config = load_config()


def _resolve_lineage(parameters):
    species = parameters.get('species', {})
    lineage = species.get('lineage') or []
    lineage_names = [item.get('scientificName', '').lower() for item in lineage if isinstance(item, dict)]

    if species.get('is_bacteria'):
        return 'bacteria_odb10'

    if 'basidiomycota' in lineage_names:
        return 'basidiomycota_odb10'
    if 'saccharomycetes' in lineage_names:
        return 'saccharomycetes_odb10'

    return 'eukaryota_odb10'


def _read_busco_summary(stats_dir, output_name):
    json_pattern = os.path.join(stats_dir, output_name, '**', 'short_summary*.json')
    summary_json_files = glob.glob(json_pattern, recursive=True)
    for json_file_path in summary_json_files:
        try:
            with open(json_file_path, 'r') as summary_file:
                return json.load(summary_file)
        except Exception:
            # BUSCO can leave a partial/corrupt json when it crashes during serialization.
            continue

    txt_pattern = os.path.join(stats_dir, output_name, '**', 'short_summary*.txt')
    summary_txt_files = glob.glob(txt_pattern, recursive=True)
    if not summary_txt_files:
        return {}

    with open(summary_txt_files[0], 'r') as summary_file:
        summary_text = summary_file.read().strip()

    if not summary_text:
        return {}

    parsed_summary = {'raw_summary': summary_text}

    # Example line:
    # C:99.6%[S:95.7%,D:3.9%],F:0.4%,M:0.0%,n:255,E:7.9%
    score_match = re.search(
        r'C:(?P<C>[\d.]+)%\[S:(?P<S>[\d.]+)%,D:(?P<D>[\d.]+)%\],'
        r'F:(?P<F>[\d.]+)%,M:(?P<M>[\d.]+)%,n:(?P<n>\d+)(?:,E:(?P<E>[\d.]+)%)?',
        summary_text,
    )
    if score_match:
        score_data = score_match.groupdict()
        parsed_summary['scores'] = {
            'C': float(score_data['C']),
            'S': float(score_data['S']),
            'D': float(score_data['D']),
            'F': float(score_data['F']),
            'M': float(score_data['M']),
            'n': int(score_data['n']),
        }
        if score_data.get('E') is not None:
            parsed_summary['scores']['E'] = float(score_data['E'])

    return parsed_summary


def _output_json_path(run_id, mode):
    file_name = 'Busco_genome.json' if mode == 'genome' else 'Busco_annotation.json'
    return os.path.join(config['BROWNOTATE_PATH'], 'runs', str(run_id), file_name)


def _resolve_input_file_path(input_file):
    if not input_file:
        return None
    if os.path.isabs(input_file):
        return input_file
    return os.path.join(config['BROWNOTATE_PATH'], input_file)


@run_busco_bp.route('/run_busco', methods=['POST'])
def run_busco():
    start_time = timer.start()

    parameters = request.json.get('parameters')
    input_file = request.json.get('input_file')
    mode = request.json.get('mode', 'genome')

    run_id = int(parameters['id'])
    cpus = int(parameters.get('cpus') or 0) or os.cpu_count() or 1
    step_payload = {'mode': mode}
    mark_step_running(run_id, 'busco', payload=step_payload)

    stats_dir = os.path.join(config['BROWNOTATE_PATH'], 'runs', str(run_id), 'stats')
    os.makedirs(stats_dir, exist_ok=True)

    resolved_input_file = _resolve_input_file_path(input_file)
    if not resolved_input_file or not os.path.exists(resolved_input_file):
        elapsed = timer.stop(start_time)
        mark_step_error(run_id, 'busco', f'BUSCO input file does not exist: {resolved_input_file}', payload=step_payload)
        return jsonify({
            'status': 'error',
            'message': f'BUSCO input file does not exist: {resolved_input_file}',
            'timer': elapsed,
        }), 400

    lineage = _resolve_lineage(parameters)
    output_name = f'busco_{mode}'

    command = (
        f'busco -i {shlex.quote(resolved_input_file)} '
        f'-m {mode} '
        f'-l {lineage} '
        f'-o {output_name} '
        f'--cpu {cpus} --force'
    )

    stdout_path = os.path.join(stats_dir, f'busco_{mode}.out')
    stderr_path = os.path.join(stats_dir, f'busco_{mode}.err')
    stdout, stderr, returncode = run_command(
        command,
        run_id,
        cpus=cpus,
        cwd=stats_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )

    # BUSCO can fail at final JSON export (e.g. float32 serialization) after producing valid summaries.
    summary_data = _read_busco_summary(stats_dir, output_name)

    if returncode != 0:
        if summary_data:
            elapsed = timer.stop(start_time)
            output_json = _output_json_path(run_id, mode)
            with open(output_json, 'w') as output_file:
                json.dump(summary_data, output_file)
            mark_step_success(run_id, 'busco', result=summary_data, timer_value=elapsed, payload=step_payload)
            return jsonify({
                'status': 'success',
                'data': summary_data,
                'timer': elapsed,
                'warning': 'BUSCO returned non-zero but summary output was recovered from run artifacts.'
            }), 200

        elapsed = timer.stop(start_time)
        mark_step_error(run_id, 'busco', 'BUSCO command failed', payload=step_payload)
        return jsonify({
            'status': 'error',
            'message': 'BUSCO command failed',
            'command': command,
            'stdout': stdout,
            'stderr': stderr,
            'timer': elapsed,
        }), 500

    output_json = _output_json_path(run_id, mode)
    with open(output_json, 'w') as output_file:
        json.dump(summary_data, output_file)

    elapsed = timer.stop(start_time)
    mark_step_success(run_id, 'busco', result=summary_data, timer_value=elapsed, payload=step_payload)
    return jsonify({
        'status': 'success',
        'data': summary_data,
        'timer': elapsed,
    }), 200
