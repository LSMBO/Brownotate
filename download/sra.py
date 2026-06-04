import subprocess
import os
import json
import shlex
from timer import timer
from flask_app.utils import load_config
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
                    return {
                        'success': False,
                        'stdout': stdout_data.decode('utf-8') if stdout_data else '',
                        'stderr': stderr_data.decode('utf-8') if stderr_data else '',
                        'returncode': process.returncode,
                    }
        except Exception as e:
            retry_count += 1
            print(f"Error while executing command: {e}. Retrying... ({retry_count}/5)")
            if process_id:
                remove_process(process_id)

    if not success:
        print("Failed to execute command after 5 attempts.")
        return {
            'success': False,
            'stdout': stdout_data.decode('utf-8') if stdout_data else '',
            'stderr': stderr_data.decode('utf-8') if stderr_data else '',
            'returncode': process.returncode if 'process' in locals() and process else 1,
        }
    
    remove_process(process_id)
    return {
        'success': True,
        'stdout': stdout_data.decode('utf-8') if stdout_data else '',
        'stderr': stderr_data.decode('utf-8') if stderr_data else '',
        'returncode': 0,
    }


@download_sra_bp.route('/download_sra', methods=['POST'])
def download_sra():
    start_time = timer.start()
    parameters = request.json.get('parameters') or {}
    wd = parameters.get('id') or request.json.get('run_id')
    if wd is None:
        return jsonify({'status': 'error', 'message': 'Missing run id', 'timer': timer.stop(start_time)}), 400

    start_section = parameters.get('startSection', {}) or {}
    is_rna = bool(start_section.get('rnaSequencing'))
    sequencing_run_list = start_section.get('rnaSequencingRunList' if is_rna else 'sequencingRunList', [])
    if not sequencing_run_list:
        return jsonify({'status': 'error', 'message': 'No sequencing runs provided', 'timer': timer.stop(start_time)}), 400

    wd = int(wd)
    commands = []
    fastq_files = []

    env['TMPDIR'] = f"runs/{wd}"
    
    for run_data in sequencing_run_list:
        accession = run_data["accession"]
        platform = run_data["platform"]
        layout = str(run_data.get("layout", "SINGLE")).upper()

        # A previous interrupted prefetch can leave a stale lock file and make
        # immediate retries fail with a generic prefetch error.
        stale_lock_path = f"runs/{wd}/seq/{accession}.sra.lock"
        if os.path.exists(stale_lock_path):
            try:
                os.remove(stale_lock_path)
            except OSError:
                pass

        prefetch_cmd = f"prefetch {accession} -o runs/{wd}/seq/{accession}.sra --max-size 1500G"
        prefetch_result = run_command(prefetch_cmd, env, wd)
        if not prefetch_result.get('success'):
            print(f"Prefetch failed for {accession}")
            prefetch_detail = (prefetch_result.get('stderr') or prefetch_result.get('stdout') or '').strip()
            prefetch_tail = '\n'.join(prefetch_detail.splitlines()[-20:]) if prefetch_detail else ''
            return jsonify({
                'status': 'error', 
                'message': f'Prefetch failed for {accession}',
                'detail': prefetch_tail,
                'returncode': prefetch_result.get('returncode'),
                "timer": timer.stop(start_time)
            }), 500

        if platform in ["ILLUMINA", "ION_TORRENT", "454", "BGISEQ", "OXFORD_NANOPORE", "PACBIO_SMRT"]:
            if layout == "PAIRED":
                fasterqdump_cmd = f"fasterq-dump runs/{wd}/seq/{accession}.sra --outdir runs/{wd}/seq --skip-technical --split-files --temp runs/{wd}/seq"
            else:
                fasterqdump_cmd = f"fasterq-dump runs/{wd}/seq/{accession}.sra --outdir runs/{wd}/seq --skip-technical --temp runs/{wd}/seq"
            fasterqdump_result = run_command(fasterqdump_cmd, env, wd)
            if not fasterqdump_result.get('success'):
                fasterq_detail = (fasterqdump_result.get('stderr') or fasterqdump_result.get('stdout') or '').strip()
                fasterq_tail = '\n'.join(fasterq_detail.splitlines()[-20:]) if fasterq_detail else ''
                return jsonify({
                    'status': 'error', 
                    'message': f'fasterq-dump failed for {accession}',
                    'detail': fasterq_tail,
                    'returncode': fasterqdump_result.get('returncode'),
                    "timer": timer.stop(start_time)
                }), 500
                
            if layout == "PAIRED":
                fq1 = f"runs/{wd}/seq/{accession}_1.fastq"
                fq2 = f"runs/{wd}/seq/{accession}_2.fastq"
                if not os.path.exists(fq2):
                    for file in os.listdir(f"runs/{wd}/seq"):
                        if file.startswith(accession) and file.endswith(".fastq") and file != f"{accession}_1.fastq":
                            os.rename(f"runs/{wd}/seq/{file}", fq2)
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