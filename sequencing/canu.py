import subprocess
import os
import shutil
from timer import timer
from flask_app.utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_docker_command
from database_search.sequencing.genome_estimation import estimate_genome_size, format_genome_size_for_canu

run_canu_bp = Blueprint('run_canu_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

# CANU Docker image
CANU_DOCKER_IMAGE = 'quay.io/biocontainers/canu:2.2--ha47f30e_0'

@run_canu_bp.route('/run_canu', methods=['POST'])
def run_canu():
    start_time = timer.start()
    command_str = ''  # Initialize to avoid issues in exception handler
    
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    scientific_name = parameters['species']['scientificName']
    sequencing_file_list = request.json.get('sequencing_file_list')
    
    # Estimate genome size from taxonomy
    # Convert parameters['species'] format to match estimate_genome_size expectations
    taxonomy_for_estimation = {
        'scientificName': parameters['species'].get('scientificName'),
        'taxonId': parameters['species'].get('taxonID') or parameters['species'].get('taxonId'),  # Handle both formats
        'lineage': parameters['species'].get('lineage', [])
    }
    
    genome_size_estimation = estimate_genome_size(taxonomy_for_estimation)
    if genome_size_estimation:
        genome_size_str = format_genome_size_for_canu(genome_size_estimation['mean'])
        print(f"Estimated genome size: {genome_size_str} ({genome_size_estimation['mean']:.0f} bp)")
    else:
        # Fallback to default if estimation fails
        genome_size_str = "12m"
        print(f"Warning: Could not estimate genome size, using default: {genome_size_str}")
    
    output_folder = f"runs/{wd}/genome"
    os.makedirs(output_folder, exist_ok=True)
    
    prefix = scientific_name.replace(' ','_')
    canu_output_dir = f"runs/{wd}/genome/canu_output"
    assembly_file_name = f"runs/{wd}/genome/{prefix}_canu.contigs.fasta"
    
    print(f"/run_canu sequencing_files: {sequencing_file_list}")
    
    # Collect sequencing files and convert to container paths
    seq_files_host = []
    seq_files_container = []
    platform = None
    
    for sequencing_file in sequencing_file_list:
        # CANU has its own correction and trimming - use raw files only
        file_name = sequencing_file['file_name']
        
        if isinstance(file_name, str):
            clean_name = file_name.replace('"', '').strip()
            seq_files_host.append(clean_name)
            # Convert to container path (mounted at /data)
            seq_files_container.append(f"/data/{clean_name}")
        else:
            # Paired files - use both
            for f in file_name:
                clean_name = f.replace('"', '').strip()
                seq_files_host.append(clean_name)
                seq_files_container.append(f"/data/{clean_name}")
        
        if platform is None:
            platform = sequencing_file['platform']
    
    # Determine technology flag
    if platform == 'PACBIO_SMRT':
        technology = '-pacbio'
    elif platform == 'OXFORD_NANOPORE':
        technology = '-nanopore'
    else:
        return jsonify({
            'status': 'error', 
            'message': f'Unsupported platform for CANU: {platform}',
            'timer': timer.stop(start_time)
        }), 400
    
    # Build CANU command with container paths
    # CANU will always run full pipeline: correction, trimming, and assembly
    container_output_dir = f"/data/runs/{wd}/genome/canu_output"
    command = [
        'canu',
        '-p', prefix,
        '-d', container_output_dir,
        f'genomeSize={genome_size_str}',
        f'maxThreads={cpus}',
        technology
    ]
    command.extend(seq_files_container)
    command_str = ' '.join(command)
    print(f"CANU command: {command_str}")
    
    # Clean up previous run if exists
    if os.path.exists(canu_output_dir):
        shutil.rmtree(canu_output_dir)
    
    try:
        # Get absolute path to current working directory for Docker volume mount
        current_dir = os.getcwd()
        
        # Setup volume mounts (mount current directory to /data in container)
        volumes = {
            current_dir: '/data'
        }
        
        # Run CANU command in Docker
        stdout, stderr, returncode = run_docker_command(
            image=CANU_DOCKER_IMAGE,
            command=command_str,
            wd=wd,
            cpus=cpus,
            volumes=volumes,
            working_dir='/data',
            timeout=2592000
        )
        
        if returncode != 0:
            return jsonify({
                'status': 'error',
                'message': f'CANU failed with return code {returncode}',
                'command': command_str,
                'stdout': stdout,
                'stderr': stderr,
                'timer': timer.stop(start_time)
            }), 500
        
        # Find the assembly file (CANU creates prefix.contigs.fasta)
        expected_canu_output = f"{canu_output_dir}/{prefix}.contigs.fasta"
        if os.path.exists(expected_canu_output):
            # Copy to final location
            shutil.copy(expected_canu_output, assembly_file_name)
        else:
            # Try alternative names
            for possible_name in [f"{prefix}.contigs.fasta", "final.contigs.fasta", "contigs.fasta"]:
                possible_path = f"{canu_output_dir}/{possible_name}"
                if os.path.exists(possible_path):
                    shutil.copy(possible_path, assembly_file_name)
                    break
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'CANU completed but assembly file not found in {canu_output_dir}',
                    'command': command_str,
                    'stdout': stdout,
                    'stderr': stderr,
                    'timer': timer.stop(start_time)
                }), 500
        
        # Clean up processed sequencing files
        for file in seq_files_host:
            if os.path.exists(file) and str(wd) in file:
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"Warning: Could not remove {file}: {str(e)}")
        
        # Keep log but remove temp files
        log_copied = False
        if os.path.exists(f"{canu_output_dir}/canu.log"):
            try:
                shutil.copy(f"{canu_output_dir}/canu.log", f"{output_folder}/canu.log")
                log_copied = True
            except Exception as e:
                print(f"Warning: Could not copy log file: {str(e)}")
        
        # Clean up working directory
        cleanup_success = False
        if os.path.exists(canu_output_dir):
            try:
                shutil.rmtree(canu_output_dir)
                cleanup_success = True
            except Exception as e:
                print(f"Warning: Could not remove canu_output_dir, it may be locked: {str(e)}")
        
        return jsonify({
            'status': 'success', 
            'data': assembly_file_name, 
            'command': command_str,
            'stdout': stdout,
            'stderr': stderr,
            'cleanup_warning': None if cleanup_success else 'Could not clean up working directory (may be locked)',
            'timer': timer.stop(start_time)
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error running CANU: {str(e)}',
            'command': command_str,
            'timer': timer.stop(start_time)
        }), 500
