import time
import os
import copy
from timer import timer
from flask_app.utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command
from flask_app.step_status import mark_step_error, mark_step_running, mark_step_success

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


def _safe_remove(path):
    if not path:
        return
    clean_path = path[1:-1] if isinstance(path, str) and len(path) > 1 and path[0] == '"' and path[-1] == '"' else path
    if os.path.exists(clean_path):
        os.remove(clean_path)


@run_fastp_bp.route('/run_fastp', methods=['POST'])
def run_fastp():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    sequencing_file_list = request.json.get('sequencing_file_list')
    mark_step_running(wd, 'fastp')

    try:
        output_files = []
        if not os.path.exists(f"runs/{wd}/seq"):
            os.makedirs(f"runs/{wd}/seq")
        
        for sequencing_file in sequencing_file_list:
            accession = sequencing_file['accession']
            file_name = sequencing_file['file_name']
            platform = sequencing_file['platform']
            layout = 'PAIRED' if isinstance(file_name, list) and len(file_name) == 2 else 'SINGLE'
            
            # Skip fastp for PacBio and Nanopore as they need different QC tools
            if platform in ["PACBIO_SMRT", "OXFORD_NANOPORE"]:
                output_files.append(sequencing_file)
                continue

            if (layout == "PAIRED"):
                output_name = get_paired_output_name(file_name, wd)
                command = get_paired_command(file_name, output_name, cpus, wd)
            else:
                output_name = get_single_output_name(file_name, wd)
                command = get_single_command(file_name, output_name, cpus, wd)

            stdout, stderr, returncode = run_command(command, wd, cpus)
            if returncode != 0:
                elapsed = timer.stop(start_time)
                mark_step_error(wd, 'fastp', f'fastp failed for {accession}')
                return jsonify({
                    'status': 'error',
                    'message': f'fastp failed for {accession}',
                    'command': command,
                    'stderr': stderr,
                    'stdout': stdout,
                    'timer': elapsed
                }), 500

            # Clean up input files when they belong to this run.
            if layout == "PAIRED":
                if str(wd) in str(file_name[0]):
                    _safe_remove(file_name[0])
                    _safe_remove(file_name[1])
            else:
                if str(wd) in str(file_name):
                    _safe_remove(file_name)

            updated_sequencing_file = copy.deepcopy(sequencing_file)
            updated_sequencing_file['fastp_file_name'] = output_name
            output_files.append(updated_sequencing_file)

        elapsed = timer.stop(start_time)
        mark_step_success(wd, 'fastp', result=output_files, timer_value=elapsed)
        print(f"retoure data: {output_files} et timer: {elapsed}")
        return jsonify({
            'status': 'success', 
            'data': output_files, 
            'timer': elapsed
        }), 200
    except Exception as exc:
        elapsed = timer.stop(start_time)
        mark_step_error(wd, 'fastp', f'Unhandled fastp error: {str(exc)}')
        return jsonify({
            'status': 'error',
            'message': f'Unhandled fastp error: {str(exc)}',
            'timer': elapsed
        }), 500


