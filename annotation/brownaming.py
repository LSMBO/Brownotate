import os
import shutil
from timer import timer
from flask_app.utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command
import glob
from flask_app.database import update_one
from flask_app.parameters_report import detect_brownotate_version
from flask_app.step_status import mark_step_error, mark_step_running, mark_step_success

run_brownaming_bp = Blueprint('run_brownaming_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNAMING_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@run_brownaming_bp.route('/run_brownaming', methods=['POST'])
def run_brownaming():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    run_id = request.json.get('run_id')
    cpus = request.json.get('cpus')
    annotation_file = request.json.get('annotation_file')
    if isinstance(annotation_file, list):
        annotation_file = annotation_file[0] if annotation_file else None
    if isinstance(annotation_file, str):
        annotation_file = annotation_file.strip().strip('"').strip("'")

    if not annotation_file or str(annotation_file).lower() == 'none' or not os.path.exists(annotation_file):
        message = f"File not found: {annotation_file}"
        mark_step_error(run_id, 'brownaming', message)
        return jsonify({'status': 'error', 'message': message}), 400

    resume = request.json.get('resume', False)
    mark_step_running(run_id, 'brownaming')

    try:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        brownotate_version = detect_brownotate_version(repo_root)
        update_one('runs', {'parameters.id': int(run_id)}, {'$set': {'resumeData.brownotate_version': brownotate_version}})
    except Exception as exc:
        print(f"[run_brownaming] failed to persist brownotate version early: {exc}")

    local_db = config.get('BROWNAMING_DB')
    if not local_db:
        mark_step_error(run_id, 'brownaming', 'BROWNAMING_DB path not configured in config file')
        return jsonify({
            'status': 'error',
            'message': 'BROWNAMING_DB path not configured in config file'
        }), 400
    
    canonical_runs_dir = os.path.join(config['BROWNOTATE_PATH'], 'runs', str(run_id), 'brownaming')
    legacy_runs_dir = os.path.join(config['BROWNOTATE_PATH'], 'Brownaming', 'runs', str(run_id))
    os.makedirs(canonical_runs_dir, exist_ok=True)
    
    if resume:
        command = f"python Brownaming/main.py --resume {run_id}"
    else:
        # Start new Brownaming run
        taxid = parameters['species']['taxonID']
        exclude = [taxo['taxid'] for taxo in parameters['brownamingSection']['excludedTaxoList']]
        last_taxid = parameters['brownamingSection'].get('lastTaxid')
        exclude_trembl = parameters['brownamingSection'].get('excludeTrembl', False)
        
        command = f"python Brownaming/main.py -p \"{annotation_file}\" -s {taxid} --run-id {run_id} --local-db \"{local_db}\" --working-dir \"{canonical_runs_dir}\""
        if cpus:
            command += f" --threads {cpus}"
        
        if exclude:
            for tax in exclude:
                command += f" --ex-tax {tax}"
        
        if last_taxid:
            command += f" --last-tax {last_taxid}"
        
        if exclude_trembl:
            command += " --swissprot-only"
        
    
    # Execute Brownaming
    stdout, stderr, returncode = run_command(command, run_id, cpus=cpus, env=env)
    
    if returncode != 0:
        elapsed = timer.stop(start_time)
        stdout_tail = '\n'.join((stdout or '').splitlines()[-20:])
        stderr_tail = '\n'.join((stderr or '').splitlines()[-20:])
        detail = f'Brownaming command failed (code={returncode})'
        if stderr_tail:
            detail += f"\nSTDERR tail:\n{stderr_tail}"
        elif stdout_tail:
            detail += f"\nSTDOUT tail:\n{stdout_tail}"
        mark_step_error(run_id, 'brownaming', detail)
        return jsonify({
            'status': 'error',
            'message': detail,
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': elapsed
        }), 500
        
    
    # Find output files
    output_files = {
        'fasta': None,
        'excel': None,
        'tsv_main': None,
        'tsv_top3': None,
        'stats': None,
        'log': None
    }
    
    # Get paths relative to Brownotate/ directory
    brownotate_path = config['BROWNOTATE_PATH']
    
    source_dir = canonical_runs_dir if os.path.isdir(canonical_runs_dir) and os.listdir(canonical_runs_dir) else legacy_runs_dir

    if os.path.isdir(source_dir) and source_dir != canonical_runs_dir:
        for src_name in os.listdir(source_dir):
            src_path = os.path.join(source_dir, src_name)
            dst_path = os.path.join(canonical_runs_dir, src_name)
            if os.path.isfile(src_path):
                try:
                    shutil.copy2(src_path, dst_path)
                except OSError:
                    pass

    for file in os.listdir(canonical_runs_dir):
        if file.endswith('_brownamed.fasta'):
            output_files['fasta'] = f'brownaming/{file}'
        elif file.endswith('_diamond_results.xlsx'):
            output_files['excel'] = f'brownaming/{file}'
        elif file.endswith('_diamond_results.tsv'):
            output_files['tsv_main'] = f'brownaming/{file}'
        elif file.endswith('_diamond_results_top3.tsv'):
            output_files['tsv_top3'] = f'brownaming/{file}'
        elif file.endswith('_brownaming_stats.png'):
            output_files['stats'] = f'brownaming/{file}'
        elif file.endswith('.log'):
            output_files['log'] = f'brownaming/{file}'

    if not output_files['fasta']:
        elapsed = timer.stop(start_time)
        detail = f'Brownaming output FASTA not found in {canonical_runs_dir}'
        mark_step_error(run_id, 'brownaming', detail)
        return jsonify({
            'status': 'error',
            'message': detail,
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': elapsed
        }), 500
    
    elapsed = timer.stop(start_time)
    result_payload = {
        'run_id': run_id,
        'output_files': output_files,
        'brownaming_dir': f'{brownotate_path}/runs/{run_id}/brownaming',
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
    }
    mark_step_success(run_id, 'brownaming', result=result_payload, timer_value=elapsed)
    return jsonify({
        'status': 'success',
        'data': result_payload,
        'run_id': run_id,
        'output_files': output_files,
        'brownaming_dir': f'{brownotate_path}/runs/{run_id}/brownaming',
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
        'timer': elapsed
    }), 200