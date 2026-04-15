import subprocess
import os
import shutil
import sys
import threading
import time
from datetime import datetime
from timer import timer
from flask_app.utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_docker_command
from flask_app.database import update_one, find_one
from flask_app.step_status import mark_step_error, mark_step_running, mark_step_success
from database_search.sequencing.genome_estimation import estimate_genome_size, format_genome_size_for_canu
from bson.int64 import Int64

def log_detailed(message):
    """Helper to log with timestamp and flush immediately"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[CANU {timestamp}] {message}", flush=True)
    sys.stdout.flush()

def update_canu_status_robust(run_id, update_data, max_retries=3):
    """
    Robustly update CANU status in database with retry logic and verification.
    
    Args:
        run_id: The run ID (will be converted to Int64 for MongoDB)
        update_data: Dictionary of fields to update
        max_retries: Maximum number of retry attempts
    
    Returns:
        bool: True if update succeeded and was verified, False otherwise
    """
    # Try both Int64 and int formats to ensure compatibility
    query_variants = [
        {"parameters.id": Int64(run_id)},
        {"parameters.id": int(run_id)}
    ]
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 2 ** (attempt - 1)
                log_detailed(f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s...")
                time.sleep(wait_time)
            
            # Try each query variant
            update_success = False
            for query in query_variants:
                log_detailed(f"Attempting update with query: {query}")
                result = update_one('runs', query, {"$set": update_data})
                
                if result['status'] == 'success':
                    log_detailed(f"Update succeeded with query type: {type(list(query.values())[0])}")
                    update_success = True
                    break
                else:
                    log_detailed(f"Update failed with this query: {result.get('message', 'Unknown error')}")
            
            if not update_success:
                log_detailed(f"All query variants failed on attempt {attempt + 1}")
                continue
            
            # CRITICAL: Verify the update actually worked by reading back
            time.sleep(0.5)  # Brief pause to ensure DB consistency
            for query in query_variants:
                verify = find_one('runs', query)
                if verify['status'] == 'success' and verify['data']:
                    # Check that the key field was actually updated
                    if 'canu_status' in update_data:
                        actual_status = verify['data'].get('resumeData', {}).get('canu_status')
                        expected_status = update_data.get('resumeData.canu_status')
                        
                        if actual_status == expected_status:
                            log_detailed(f"✓ Verification PASSED: canu_status is '{actual_status}'")
                            return True
                        else:
                            log_detailed(f"✗ Verification FAILED: expected '{expected_status}', got '{actual_status}'")
                    else:
                        # For other updates, just verify the record exists
                        log_detailed(f"✓ Verification PASSED: record found")
                        return True
            
            log_detailed(f"Verification failed on attempt {attempt + 1}")
            
        except Exception as e:
            log_detailed(f"Exception during update attempt {attempt + 1}: {str(e)}")
            import traceback
            log_detailed(traceback.format_exc())
    
    log_detailed(f"✗ Update FAILED after {max_retries} attempts")
    return False

run_canu_bp = Blueprint('run_canu_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

# CANU Docker image
CANU_DOCKER_IMAGE = 'quay.io/biocontainers/canu:2.2--ha47f30e_0'

def run_canu_background(wd, cpus, scientific_name, sequencing_file_list, genome_size_str, platform):
    start_time = timer.start()
    command_str = ''
    
    try:
        # Keep CANU-specific status for backward compatibility and write unified step status for polling.
        log_detailed(f"[Background] Setting status to 'running' for run {wd}")
        if not update_canu_status_robust(wd, {"resumeData.canu_status": "running"}):
            log_detailed(f"[Background] CRITICAL: Failed to set initial status for run {wd}")
            return
        mark_step_running(wd, 'canu')
        
        output_folder = f"runs/{wd}/genome"
        os.makedirs(output_folder, exist_ok=True)
        
        prefix = scientific_name.replace(' ','_')
        canu_output_dir = f"runs/{wd}/genome/canu_output"
        assembly_file_name = f"runs/{wd}/genome/{prefix}_canu.contigs.fasta"
        stdout_log_file = f"{output_folder}/canu_stdout.log"
        stderr_log_file = f"{output_folder}/canu_stderr.log"
        
        seq_files_host = []
        seq_files_container = []
        
        for sequencing_file in sequencing_file_list:
            file_name = sequencing_file['file_name']
            if isinstance(file_name, str):
                clean_name = file_name.replace('"', '').strip()
                seq_files_host.append(clean_name)
                seq_files_container.append(f"/data/{clean_name}")
            else:
                for f in file_name:
                    clean_name = f.replace('"', '').strip()
                    seq_files_host.append(clean_name)
                    seq_files_container.append(f"/data/{clean_name}")
        
        if platform == 'PACBIO_SMRT':
            technology = '-pacbio'
        elif platform == 'OXFORD_NANOPORE':
            technology = '-nanopore'
        else:
            update_one('runs', {"parameters.id": int(wd)}, {"$set": {
                "resumeData.canu_status": "error",
                "resumeData.canu_error": f'Unsupported platform: {platform}'
            }})
            return
        
        container_output_dir = f"/data/runs/{wd}/genome/canu_output"
        command = [
            'canu', '-p', prefix, '-d', container_output_dir,
            f'genomeSize={genome_size_str}', f'maxThreads={cpus}',
            'stopOnLowCoverage=5', technology
        ]
        command.extend(seq_files_container)
        command_str = ' '.join(command)
        
        if os.path.exists(canu_output_dir):
            shutil.rmtree(canu_output_dir)
        
        current_dir = os.getcwd()
        volumes = {current_dir: '/data'}
        
        log_detailed(f"[Background] Starting CANU for run {wd}")
        
        stdout, stderr, returncode = run_docker_command(
            image=CANU_DOCKER_IMAGE, command=command_str, wd=wd,
            cpus=cpus, volumes=volumes, working_dir='/data', timeout=2592000
        )
        
        with open(stdout_log_file, 'w') as f:
            f.write(stdout if stdout else "No stdout\n")
        with open(stderr_log_file, 'w') as f:
            f.write(stderr if stderr else "No stderr\n")
        
        if returncode != 0:
            log_detailed(f"[Background] CANU failed with return code {returncode}, updating database...")
            update_canu_status_robust(wd, {
                "resumeData.canu_status": "error",
                "resumeData.canu_error": f'CANU failed with return code {returncode}',
                "resumeData.stdout_file": stdout_log_file,
                "resumeData.stderr_file": stderr_log_file
            })
            mark_step_error(wd, 'canu', f'CANU failed with return code {returncode}')
            log_detailed(f"[Background] CANU failed for run {wd}")
            return
        
        expected_canu_output = f"{canu_output_dir}/{prefix}.contigs.fasta"
        if os.path.exists(expected_canu_output):
            shutil.copy(expected_canu_output, assembly_file_name)
        else:
            for possible_name in [f"{prefix}.contigs.fasta", "final.contigs.fasta", "contigs.fasta"]:
                possible_path = f"{canu_output_dir}/{possible_name}"
                if os.path.exists(possible_path):
                    shutil.copy(possible_path, assembly_file_name)
                    break
            else:
                log_detailed(f"[Background] Assembly file not found, updating database...")
                update_canu_status_robust(wd, {
                    "resumeData.canu_status": "error",
                    "resumeData.canu_error": "Assembly file not found",
                    "resumeData.stdout_file": stdout_log_file,
                    "resumeData.stderr_file": stderr_log_file
                })
                mark_step_error(wd, 'canu', 'Assembly file not found')
                log_detailed(f"[Background] Assembly file not found for run {wd}")
                return
        
        for file in seq_files_host:
            if os.path.exists(file) and str(wd) in file:
                try:
                    os.remove(file)
                except Exception:
                    pass
        
        if os.path.exists(f"{canu_output_dir}/canu.log"):
            shutil.copy(f"{canu_output_dir}/canu.log", f"{output_folder}/canu.log")
        
        if os.path.exists(canu_output_dir):
            shutil.rmtree(canu_output_dir)
        
        elapsed = timer.stop(start_time)
        
        log_detailed(f"[Background] Updating database for run {wd}...")
        update_success = update_canu_status_robust(wd, {
            "resumeData.canu_status": "completed",
            "resumeData.assemblyFile": assembly_file_name,
            "resumeData.stdout_file": stdout_log_file,
            "resumeData.stderr_file": stderr_log_file,
            "timers.Running CANU assembly ": elapsed
        })
        mark_step_success(wd, 'canu', result=assembly_file_name, timer_value=elapsed)
        
        if update_success:
            log_detailed(f"[Background] ✓ Database updated AND VERIFIED for run {wd}")
        else:
            log_detailed(f"[Background] ✗ CRITICAL: Database update could not be verified for run {wd}")
            log_detailed(f"[Background] ✗ Manual intervention may be required")
        
        log_detailed(f"[Background] CANU completed for run {wd} in {elapsed}")
        
    except Exception as e:
        import traceback
        error_msg = f"Exception: {str(e)}"
        log_detailed(f"[Background] CANU exception for run {wd}: {error_msg}")
        log_detailed(traceback.format_exc())
        update_canu_status_robust(wd, {
            "resumeData.canu_status": "error",
            "resumeData.canu_error": error_msg
        })
        mark_step_error(wd, 'canu', error_msg)

@run_canu_bp.route('/run_canu', methods=['POST'])
def run_canu():
    log_detailed("CANU route called - Starting async execution")
    
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    scientific_name = parameters['species']['scientificName']
    sequencing_file_list = request.json.get('sequencing_file_list')
    
    taxonomy_for_estimation = {
        'scientificName': parameters['species'].get('scientificName'),
        'taxonId': parameters['species'].get('taxonID') or parameters['species'].get('taxonId'),
        'lineage': parameters['species'].get('lineage', [])
    }
    
    genome_size_estimation = estimate_genome_size(taxonomy_for_estimation)
    if genome_size_estimation:
        genome_size_str = format_genome_size_for_canu(genome_size_estimation['mean'])
    else:
        genome_size_str = "12m"
    
    platform = None
    for sequencing_file in sequencing_file_list:
        if platform is None:
            platform = sequencing_file.get('platform')
    
    if not platform:
        return jsonify({
            'status': 'error',
            'message': 'Platform not specified in sequencing files'
        }), 400
    
    thread = threading.Thread(
        target=run_canu_background,
        args=(wd, cpus, scientific_name, sequencing_file_list, genome_size_str, platform)
    )
    thread.daemon = True
    thread.start()
    
    log_detailed(f"CANU started in background for run {wd}")
    
    return jsonify({
        'status': 'started',
        'message': 'CANU assembly started in background',
        'run_id': wd
    }), 200

@run_canu_bp.route('/check_canu_status/<int:run_id>', methods=['GET'])
def check_canu_status(run_id):
    result = find_one('runs', {'parameters.id': run_id})
    
    if result['status'] != 'success' or not result['data']:
        return jsonify({'status': 'error', 'message': 'Run not found'}), 404
    
    run_data = result['data']
    resume_data = run_data.get('resumeData', {})
    canu_status = resume_data.get('canu_status', 'not_started')
    
    response = {'status': canu_status}
    
    if canu_status == 'completed':
        response['assemblyFile'] = resume_data.get('assemblyFile')
        response['timer'] = run_data.get('timers', {}).get('Running CANU assembly ...')
        response['stdout_file'] = resume_data.get('stdout_file')
        response['stderr_file'] = resume_data.get('stderr_file')
    elif canu_status == 'error':
        response['error'] = resume_data.get('canu_error', 'Unknown error')
        response['stdout_file'] = resume_data.get('stdout_file')
        response['stderr_file'] = resume_data.get('stderr_file')
    
    return jsonify(response), 200
