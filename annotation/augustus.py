import subprocess
import os
import multiprocessing
import shutil
from Bio import SeqIO
import json
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
import shutil
from flask_app.commands import run_command

run_augustus_bp = Blueprint('run_augustus_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"


@run_augustus_bp.route('/run_augustus', methods=['POST'])
def run_augustus():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    split_assembly_files = request.json.get('split_assembly_files')
    wd = parameters['id']
    
    current_dir = os.getcwd()
    work_dir = f"runs/{wd}/annotation/augustus"
    os.makedirs(work_dir, exist_ok=True)

    scientific_name = parameters['species']['scientificName']
    annotation_concatenated_file = f"runs/{wd}/annotation/{scientific_name.replace(' ', '_')}_Brownotate.fasta"

    with multiprocessing.Pool() as pool:
        results = []
        for i, assembly_file in enumerate(split_assembly_files):
            output_name = f"runs/{wd}/annotation/augustus/augustus_part{i+1}"
            result = pool.apply_async(run_augustus_worker, args=(assembly_file, output_name, wd))
            results.append(result)
 
        annotation_files = []
        error_response = None
        for result in results:
            res = result.get()
            if isinstance(res, dict) and res.get('status') == 'error':
                error_response = res
                break
            annotation_files.append(res)

        if error_response:
            return jsonify({
                'status': 'error',
                'message': 'Augustus command failed',
                'command': error_response.get('command'),
                'stdout': error_response.get('stdout'),
                'stderr': error_response.get('stderr'),
                'timer': timer.stop(start_time)
            }), 500
        
        concatenate_files(annotation_files, wd, annotation_concatenated_file)
        # clean(split_assembly_files, wd)
                
        
        return jsonify({
            'status': 'success', 
            'data': annotation_concatenated_file, 
            'timer': timer.stop(start_time)
        }), 200
    
def run_augustus_worker(assembly_file, output_name, wd):
    output_basename = os.path.basename(output_name)
    output_aa_file = f"runs/{wd}/annotation/augustus/{output_basename}.aa"
    output_gff_file = f"runs/{wd}/annotation/augustus/{output_basename}.gff"
    if not os.path.exists(output_aa_file):
        command = f"augustus --species={wd} {assembly_file} > {output_gff_file}"
        stdout, stderr, returncode = run_command(command, wd)
        if returncode != 0:          
            return {'status': 'error', 'command': command, 'stdout': stdout, 'stderr': stderr}
                              
        command = f"perl {conda_bin_path}/getAnnoFasta.pl {output_name}.gff"
        stdout, stderr, returncode = run_command(command, wd)
        if returncode != 0:          
            return {'status': 'error', 'command': command, 'stdout': stdout, 'stderr': stderr}
                            
    return output_aa_file
              
def concatenate_files(annotation_files, wd, annotation_concatenated_file):
    seq_records = []
    count = 0
    for file in annotation_files:
        if os.path.exists(file):
            with open(file, 'r') as file_handle:
                for seq_record in SeqIO.parse(file_handle, "fasta"):
                    count += 1
                    new_id = f"augustus_predicted_{count}"
                    seq_record.id = new_id
                    seq_record.description = ""
                    seq_records.append(seq_record)
    with open(annotation_concatenated_file, 'w') as outfile:
        SeqIO.write(seq_records, outfile, "fasta")

def clean(split_assembly_files, wd):
    shutil.rmtree(f'runs/{wd}/annotation/augustus')
    for file in split_assembly_files:
        os.remove(file)

        