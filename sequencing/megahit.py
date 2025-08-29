import subprocess
import os
import shutil
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command

run_megahit_bp = Blueprint('run_megahit_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@run_megahit_bp.route('/run_megahit', methods=['POST'])
def run_megahit():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    scientific_name = parameters['species']['scientificName']
    sequencing_file_list = request.json.get('sequencing_file_list')

    if not os.path.exists(f"runs/{wd}/genome"):
        os.makedirs(f"runs/{wd}/genome")
        
    assembly_file_name = f"runs/{wd}/genome/" + scientific_name.replace(' ','_') + "_Megahit.fasta"
    
    single_seq_files = []
    paired_fwd_seq_files = []
    paired_rev_seq_files = []
    for sequencing_file in sequencing_file_list:
        accession = sequencing_file['accession']
        
        file_name = sequencing_file['file_name']
        if 'fastp_file_name' in sequencing_file:
            file_name = sequencing_file['fastp_file_name']
        if 'remove_phix_file_name' in sequencing_file:
            file_name = sequencing_file['remove_phix_file_name']
        
            
            
        platform = sequencing_file['platform']
        layout = 'PAIRED' if isinstance(file_name, list) and len(file_name) == 2 else 'SINGLE'
        

        if layout == "SINGLE":
            if file_name[0] == '"':
                file_name = file_name[1:-1]
                valid_file_name = file_name.replace('"', '').replace(' ', '_')
                os.rename(file_name, valid_file_name)                
            else:
                valid_file_name = file_name

            single_seq_files.append(valid_file_name)
            
        else:
            if file_name[0][0] == '"':
                file_name[0] = file_name[0][1:-1]
                file_name[1] = file_name[1][1:-1]
                valid_file_name = [file_name[0].replace('"', '').replace(' ', '_'), file_name[1].replace('"', '').replace(' ', '_')]
                os.rename(file_name[0], valid_file_name[0])
                os.rename(file_name[1], valid_file_name[1])
            else:
                valid_file_name = file_name

            paired_fwd_seq_files.append(valid_file_name[0])
            paired_rev_seq_files.append(valid_file_name[1])

    command_part1 = f"megahit -o runs/{wd}/genome/megahit_working_dir -t {cpus} --mem-flag 2 -m 0.9 "
    command_part_single = ""
    if len(single_seq_files)!=0:
        command_part_single = "-r "+','.join(single_seq_files)+" "
        
    command_part_paired_forward = ""
    command_part_paired_reverse = ""
    if len(paired_fwd_seq_files)!=0:
        command_part_paired_forward = "-1 "+','.join(paired_fwd_seq_files)+" "
        command_part_paired_reverse = "-2 "+','.join(paired_rev_seq_files)+" "
    
    command = command_part1 + command_part_single + command_part_paired_forward + command_part_paired_reverse

    if os.path.exists(f"runs/{wd}/genome/megahit_working_dir"):
        shutil.rmtree(f"runs/{wd}/genome/megahit_working_dir")    

    stdout, stderr, returncode = run_command(command, wd, cpus=cpus)
    if returncode == -9:
        return jsonify({
            "status": "error",
            "message": f"Megahit was killed (exit code -9). This typically happens due to out-of-memory (OOM) issues. Try running on a machine with more RAM, or reducing the size/complexity of the input data.",
            "command": command,
            "stderr": stderr,
            "stdout": stdout,
            "timer": timer.stop(start_time)
        }), 500  
    elif returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'Megahit command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500        
    
    if os.path.exists(f"runs/{wd}/genome/megahit_working_dir/final.contigs.fa"):
        os.rename(f"runs/{wd}/genome/megahit_working_dir/final.contigs.fa", assembly_file_name)
        os.rename(f"runs/{wd}/genome/megahit_working_dir/log", f"runs/{wd}/genome/megahit.log")
        shutil.rmtree(f"runs/{wd}/genome/megahit_working_dir")
    
    for file in single_seq_files + paired_fwd_seq_files + paired_rev_seq_files:
        if os.path.exists(file) and str(wd) in file:
            os.remove(file)

    return jsonify({
        'status': 'success', 
        'data': assembly_file_name, 
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
        'timer': timer.stop(start_time)
    }), 200
    
