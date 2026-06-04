from Bio import SeqIO
import os
from timer import timer
from flask_app.utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"

run_split_assembly_bp = Blueprint('run_split_assembly_bp', __name__)


def _compute_target_chunk_count(genome_size_mb, requested_cpus):
    """
    Choose a chunk count from genome size to avoid over-splitting small genomes.

    Heuristic goals:
    - very small genomes: avoid BLAT startup overhead (1-2 chunks)
    - medium genomes: moderate parallelism (4-8 chunks)
    - very large genomes: keep enough chunks for load balancing
    """
    if genome_size_mb <= 30:
        target = 1
    elif genome_size_mb <= 120:
        target = 2
    elif genome_size_mb <= 300:
        target = 4
    elif genome_size_mb <= 900:
        target = 6
    elif genome_size_mb <= 1800:
        target = 8
    else:
        target = 12

    # Avoid creating too many files when many CPUs are available.
    return max(1, min(int(requested_cpus), target))

@run_split_assembly_bp.route('/run_split_assembly', methods=['POST'])
def run_split_assembly():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = int(parameters['cpus'])
    assembly_file = request.json.get('assembly_file')

    # Create the directory if it does not exist
    if not os.path.exists(f'runs/{wd}/annotation'):
        os.makedirs(f'runs/{wd}/annotation')
    
    
    assembly_file_simplified = os.path.join(f'runs/{wd}/annotation', os.path.basename(os.path.splitext(assembly_file)[0] + '_simplified.fasta'))
    
    command = f"{conda_bin_path}/simplifyFastaHeaders.pl {assembly_file} seq '{assembly_file_simplified}' runs/{wd}/annotation/header.map"
    stdout, stderr, returncode = run_command(command, wd)
    if returncode != 0:
        return jsonify({
            'status': 'error',
            'message': f'simplifyFastaHeaders command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    
    
    
    fasta_records = SeqIO.parse(assembly_file_simplified, 'fasta')
    fasta_records = sorted(fasta_records, key=lambda x: len(x.seq), reverse=True)

    total_sequences = len(fasta_records)
    total_bases = sum(len(record.seq) for record in fasta_records)
    genome_size_mb = total_bases / (1024 * 1024)

    # Dynamic chunk count based on genome size, then clamp by available contigs.
    target_chunks = _compute_target_chunk_count(genome_size_mb, cpus)
    chunk_count = min(total_sequences, target_chunks)

    if chunk_count <= 0:
        return jsonify({'status': 'error', 'message': 'No sequence found in assembly file', 'timer': timer.stop(start_time)}), 500

    # Create n empty lists
    lists = [[] for i in range(chunk_count)]
    
    # Assign each record to one of the n lists
    list_idx = 0
    for record in fasta_records:
        lists[list_idx].append(record)
        list_idx = (list_idx + 1) % chunk_count
    
    # Write each list of records to a separate file
    file_names = []
    for i, record_list in enumerate(lists):
        file_name = os.path.join(f'runs/{wd}/annotation', 'file_{}.fasta'.format(i+1))
        SeqIO.write(record_list, file_name, 'fasta')
        file_names.append(file_name)
    
    return jsonify({'status': 'success', 'data': file_names, 'timer': timer.stop(start_time)}), 200
