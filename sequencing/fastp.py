import time
import os
import copy
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command

run_fastp_bp = Blueprint('run_fastp_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

  
def get_paired_command(file_name, output_name, cpus, wd):
    return f"fastp -i {file_name[0]} -w {cpus} -I {file_name[1]} -o {output_name[0]} -O {output_name[1]} -j runs/{wd}/seq/fastp/fastp_log.json -h runs/{wd}/seq/fastp/fastp_log.html --dont_eval_duplication"

def get_single_command(file_name, output_name, cpus, wd):
    return f"fastp -i {file_name} -w {cpus} -o {output_name} -j runs/{wd}/seq/fastp/fastp_log.json -h runs/{wd}/seq/fastp/fastp_log.html --dont_eval_duplication"

def get_paired_output_name(file_name, wd):
    if file_name[0][0] == '"':
        file_name[0] = file_name[0][1:-1]
        file_name[1] = file_name[1][1:-1]
    
    file1 = f"runs/{wd}/seq/" + os.path.basename(file_name[0].replace(".fq", ".fastq"))
    file1 = file1.replace(".fastq", "_fastp.fastq")
    file2 = f"runs/{wd}/seq/" + os.path.basename(file_name[1].replace(".fq", ".fastq"))
    file2 = file2.replace(".fastq", "_fastp.fastq")
    return [f'"{file1}"', f'"{file2}"']

def get_single_output_name(file_name, wd):
    if file_name[0] == '"':
        file_name = file_name[1:-1]
    
    file_name = f"runs/{wd}/seq/" + os.path.basename(file_name.replace(".fq", ".fastq"))
    file_name = file_name.replace(".fastq", "_fastp.fastq")
    return f'"{file_name}"'


@run_fastp_bp.route('/run_fastp', methods=['POST'])
def run_fastp():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    sequencing_file_list = request.json.get('sequencing_file_list')

    output_files = []
    if not os.path.exists(f"runs/{wd}/seq"):
        os.makedirs(f"runs/{wd}/seq")
    
    for sequencing_file in sequencing_file_list:
        accession = sequencing_file['accession']
        file_name = sequencing_file['file_name']
        platform = sequencing_file['platform']
        layout = 'PAIRED' if isinstance(file_name, list) and len(file_name) == 2 else 'SINGLE'
        if platform == "PACBIO_SMRT":
            continue

        if (layout == "PAIRED"):
            output_name = get_paired_output_name(file_name, wd)
            command = get_paired_command(file_name, output_name, cpus, wd)
        else:
            output_name = get_single_output_name(file_name, wd)
            command = get_single_command(file_name, output_name, cpus, wd)

        stdout, stderr, returncode = run_command(command, wd, cpus)
        if returncode != 0:
            return jsonify({
                'status': 'error',
                'message': f'fastp failed for {accession}',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 500

        # Clean up
        if layout == "PAIRED":
            if str(wd) in file_name[0]:
                os.remove(file_name[0])
                os.remove(file_name[1])
        else:
            if str(wd) in file_name:
                os.remove(file_name)

        updated_sequencing_file = copy.deepcopy(sequencing_file)
        updated_sequencing_file['fastp_file_name'] = output_name

        output_files.append(updated_sequencing_file)
    print(f"retoure data: {output_files} et timer: {timer.stop(start_time)}")
    return jsonify({
        'status': 'success', 
        'data': output_files, 
        'timer': timer.stop(start_time)
    }), 200


