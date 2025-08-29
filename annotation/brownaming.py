import os
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
import shutil
from flask_app.commands import run_command

run_brownaming_bp = Blueprint('run_brownaming_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


@run_brownaming_bp.route('/run_brownaming', methods=['POST'])
def run_brownaming():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    annotation_file = request.json.get('annotation_file')
    taxid = parameters['species']['taxonID']
    scientific_name = parameters['species']['scientificName']
    output_name = f"{scientific_name.replace(' ', '_')}_Brownotate.fasta"
    directory_name = f"runs/{wd}/brownaming"
    exclude = [taxo['taxid'] for taxo in parameters['brownamingSection']['excludedTaxoList']]
    max_rank = parameters['brownamingSection']['highestRank']
    
    # temp code to fake the process
    # shutil.copytree('runs/fake_run/brownaming', directory_name)
    # os.rename(annotation_file, os.path.join(directory_name, output_name))
    # return jsonify({'status': 'success', 'data': os.path.join(directory_name, output_name), 'timer': timer.stop(start_time)}), 200
    ##
    
    if os.path.exists(directory_name + "/run_id.txt"):
        with open(directory_name + "/run_id.txt", 'r') as run_id_file:
            resume = run_id_file.readline().strip()
    
        command = f"python Brownaming-1.0.0/main.py --resume {resume}"
        stdout, stderr, returncode = run_command(command, wd, cpus=cpus)
        if returncode != 0:          
            return jsonify({
                'status': 'error',
                'message': f'Brownaming resume command failed',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 500    
    
    else:
        directory_name = os.path.abspath(directory_name)
        output_name = os.path.basename(output_name)
        command = f"python Brownaming-1.0.0/main.py -p \"{annotation_file}\" -s \"{taxid}\" -o {output_name} -dir {directory_name} -c {cpus}"
        if exclude:
            for tax in exclude:
                command = command + f" -e {tax}"
        if max_rank:
            command = command + f" -mr {max_rank}"

        stdout, stderr, returncode = run_command(command, wd, cpus=cpus)
        if returncode != 0:          
            return jsonify({
                'status': 'error',
                'message': f'Brownaming command failed',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 500    

        return jsonify({
            'status': 'success', 
            'data': os.path.join(directory_name, output_name), 
            'command': command,
            'stdout': stdout,
            'stderr': stderr,
            'timer': timer.stop(start_time)
        }), 200