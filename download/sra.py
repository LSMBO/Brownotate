import subprocess
import os
import json
import shlex
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.file_ops import create_download_folder
from flask_app.process_manager import add_process, remove_process
from flask_app.database import find_one

download_sra_bp = Blueprint('download_sra_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['SRA_DOWNLOAD_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


def run_command(command, env, wd):
    if isAnnotationInProgress(wd) == False:
        print("Annotation canceled. Stopping command execution.")
        return None, None
    # env['TMPDIR'] = f'runs/{wd}/tmp'
    retry_count = 0
    success = False
    stdout_data, stderr_data = None, None
    process_id = None

    while retry_count < 5 and not success:
        try:
            print(f"\n{command}")
            command_args = shlex.split(command)
            process = subprocess.Popen(command_args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
            process_id = process.pid
            add_process(wd, process_id, command, 1)
            stdout_data, stderr_data = process.communicate()
            if process.returncode == 0:
                success = True
            else:
                if isAnnotationInProgress(wd):
                    retry_count += 1
                    print(f"Command failed with return code {process.returncode}. Retrying... ({retry_count}/5)")
                else:
                    print(f"Annotation canceled. Stopping retries.")
                    return None, None
        except Exception as e:
            retry_count += 1
            print(f"Error while executing command: {e}. Retrying... ({retry_count}/5)")
            if process_id:
                remove_process(process_id)

    if not success:
        print("Failed to execute command after 5 attempts.")
        return None, None
    return stdout_data.decode('utf-8'), stderr_data.decode('utf-8')


@download_sra_bp.route('/download_sra', methods=['POST'])
def download_sra():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    sequencing_run_list = parameters['startSection']['sequencingRunList']
    commands = []
    fastq_files = []

    env['TMPDIR'] = f"runs/{wd}"
    
    for run_data in sequencing_run_list:
        accession = run_data["accession"]
        platform = run_data["platform"]
        layout = run_data["layout"]

        prefetch_cmd = f"prefetch {accession} -o runs/{wd}/seq/{accession}.sra --max-size 1500G"
        if not run_command(prefetch_cmd, env, wd):
            print(f"Prefetch failed for {accession}")
            return jsonify({
                'status': 'error', 
                'message': f'Prefetch failed for {accession}', 
                "timer": timer.stop(start_time)
            }), 500

        if platform in ["ILLUMINA", "ION_TORRENT", "454", "BGISEQ", "OXFORD_NANOPORE", "PACBIO_SMRT"]:
            if layout == "PAIRED":
                fasterqdump_cmd = f"fasterq-dump runs/{wd}/seq/{accession}.sra --outdir runs/{wd}/seq --skip-technical --split-files --temp runs/{wd}/seq"
            else:
                fasterqdump_cmd = f"fasterq-dump runs/{wd}/seq/{accession}.sra --outdir runs/{wd}/seq --skip-technical --temp runs/{wd}/seq"
            if not run_command(fasterqdump_cmd, env, wd):
                return jsonify({
                    'status': 'error', 
                    'message': f'fasterq-dump failed for {accession}', 
                    "timer": timer.stop(start_time)
                }), 500
                
            if layout == "PAIRED":
                fq1 = f"runs/{wd}/seq/{accession}_1.fastq"
                fq2 = f"runs/{wd}/seq/{accession}_2.fastq"
                if not os.path.exists(fq2):
                    for file in os.listdir(f"runs/{wd}/seq"):
                        if file.startswith(accession) and file.endswith(".fastq") and file != f"{accession}_1.fastq":
                            os.rename(f"seq/{file}", fq2)
                            break
                fastq_files.append({
                    "accession": accession,
                    "file_name": [f"runs/{wd}/seq/{accession}_1.fastq", f"runs/{wd}/seq/{accession}_2.fastq"],
                    "platform": platform
                })
            else:
                fastq_files.append({"accession": accession, "file_name": f"runs/{wd}/seq/{accession}.fastq", "platform": platform})
        else:
            return jsonify({
                'status': 'error', 
                'message': f'Platform {platform} not supported for {accession}', 
                "timer": timer.stop(start_time)
            }), 400

    return jsonify({
        'status': 'success', 
        'data': fastq_files,
        "timer": timer.stop(start_time)
    }), 200


def isAnnotationInProgress(run_id):
    run_results = find_one('runs', {'parameters.id': int(run_id)})
    if run_results and run_results['data']:
        return True
    return False