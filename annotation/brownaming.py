import os
from timer import timer
from flask_app.utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command
import glob

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
    resume = request.json.get('resume', False)

    local_db = config.get('BROWNAMING_DB')
    if not local_db:
        return jsonify({
            'status': 'error',
            'message': 'BROWNAMING_DB path not configured in config file'
        }), 400
    
    brownaming_runs_dir = os.path.join(config['BROWNOTATE_PATH'], 'runs', str(run_id), 'brownaming')
    
    if resume:
        command = f"python Brownaming/main.py --resume {run_id}"
    else:
        # Start new Brownaming run
        taxid = parameters['species']['taxonID']
        exclude = [taxo['taxid'] for taxo in parameters['brownamingSection']['excludedTaxoList']]
        last_taxid = parameters['brownamingSection'].get('lastTaxid')
        exclude_trembl = parameters['brownamingSection'].get('excludeTrembl', False)
        
        command = f"python Brownaming/main.py -p \"{annotation_file}\" -s {taxid} --run-id {run_id} --local-db \"{local_db}\" --working-dir \"{brownaming_runs_dir}\""
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
    
    if returncode != 0 or stdout.strip().split('\n')[-1].startswith('[ERROR]') or stderr.strip().split('\n')[-1].startswith('[ERROR]'):
        return jsonify({
            'status': 'error',
            'message': 'Brownaming command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500
        
    
    # Find output files
    output_files = {
        'fasta': None,
        'excel': None,
        'stats': None,
        'log': None
    }
    
    # Get paths relative to Brownotate/ directory
    brownotate_path = config['BROWNOTATE_PATH']
    
    for file in os.listdir(brownaming_runs_dir):
        if file.endswith('_brownamed.fasta'):
            output_files['fasta'] = f'brownaming/{file}'
        elif file.endswith('_diamond_results.xlsx'):
            output_files['excel'] = f'brownaming/{file}'
        elif file.endswith('_brownaming_stats.png'):
            output_files['stats'] = f'brownaming/{file}'
        elif file.endswith('.log'):
            output_files['log'] = f'brownaming/{file}'
    
    return jsonify({
        'status': 'success',
        'run_id': run_id,
        'output_files': output_files,
        'brownaming_dir': f'{brownotate_path}/runs/{run_id}/brownaming',
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
        'timer': timer.stop(start_time)
    }), 200