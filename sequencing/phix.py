import os
import copy
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command

run_remove_phix_bp = Blueprint('run_remove_phix_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
       
def get_paired_command(file_name, output_name, cpus):
    return f"bowtie2 -p {cpus} -x phix/bt2_index_base -1 {file_name[0]} -2 {file_name[1]} --sensitive --un-conc {output_name} --mm -t"

def get_single_command(file_name, output_name, cpus):
    return f"bowtie2 -p {cpus} -x phix/bt2_index_base -U {file_name} --sensitive --un {output_name} --mm -t"
       
def get_output_name(file_name, layout, wd):
    if layout == "SINGLE":
        if file_name[0] == '"':
            file_name = file_name[1:-1]
        output_name = f"runs/{wd}/seq/" + os.path.basename(file_name).replace(".fq.gz", ".fastq.gz").replace(".fq", ".fastq").replace(".fastq", "_phix.fastq")
        return f'"{output_name}"'
    else:
        if file_name[0][0] == '"':
            file_name[0] = file_name[0][1:-1]
            file_name[1] = file_name[1][1:-1]
            
        if '1_fastp' in file_name[0]:
            file_name = file_name[0].replace("1_fastp", "_fastp").replace('__', '_')
        elif '1.fastq' in file_name[0]:
            file_name = file_name[0].replace("1.fastq", ".fastq").replace('__', '_')
        elif '1.fq' in file_name[0]:
            file_name = file_name[0].replace("1.fq", ".fq").replace('__', '_')
        else:
            file_name = file_name[0]
        output_name = f"runs/{wd}/seq/" + os.path.basename(file_name).replace(".fq.gz", ".fastq.gz").replace(".fq", ".fastq").replace(".fastq", "_phix.fastq")
        return f'"{output_name}"'

@run_remove_phix_bp.route('/run_remove_phix', methods=['POST'])
def run_phix():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    sequencing_file_list = request.json.get('sequencing_file_list')

    output_files = []
    seq_tmpdir = os.path.abspath(f"runs/{wd}/seq")
    if not os.path.exists(seq_tmpdir):
        os.makedirs(seq_tmpdir)

    local_env = os.environ.copy()
    local_env['TMPDIR'] = seq_tmpdir

    for sequencing_file in sequencing_file_list:
        accession = sequencing_file['accession']
        file_name = sequencing_file['fastp_file_name'] if 'fastp_file_name' in sequencing_file else sequencing_file['file_name']
        platform = sequencing_file['platform']
        layout = 'PAIRED' if isinstance(file_name, list) and len(file_name) == 2 else 'SINGLE'
        

        output_name = get_output_name(file_name, layout, wd)    
        if (layout == "PAIRED"):
            command = get_paired_command(file_name, output_name, cpus)
        else:
            layout = "SINGLE"
            command = get_single_command(file_name, output_name, cpus)
            
        bowtie_log_path = f"runs/{wd}/seq/bowtie2.log"
        bowtie_log_null = f"runs/{wd}/seq/null"
        
        stdout, stderr, returncode = run_command(command, wd, cpus=cpus, env=local_env, stdout_path=bowtie_log_null, stderr_path=bowtie_log_path)
        if returncode != 0:
            return jsonify({
                'status': 'error',
                'message': f'bowtie2 failed for {accession}',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 500        
        
        # Clean up
        if os.path.exists(f"runs/{wd}/seq/null"):
            os.remove(f"runs/{wd}/seq/null")
        
        updated_sequencing_file = copy.deepcopy(sequencing_file)
        if layout == "PAIRED":
            output_name_1 = output_name.replace("_phix.fastq", "_phix.1.fastq")
            output_name_2 = output_name.replace("_phix.fastq", "_phix.2.fastq")
            updated_sequencing_file['remove_phix_file_name'] = [output_name_1, output_name_2]
            if str(wd) in file_name[0]:
                if file_name[0][0] == '"':
                    file_name[0] = file_name[0][1:-1]
                    file_name[1] = file_name[1][1:-1]
                os.remove(file_name[0])
                os.remove(file_name[1])
        else:
            updated_sequencing_file['remove_phix_file_name'] = output_name
            if str(wd) in file_name:
                if file_name[0] == '"':
                    file_name = file_name[1:-1]
                os.remove(file_name)
                
        output_files.append(updated_sequencing_file)

    return jsonify({
        'status': 'success', 
        'data': output_files, 
        'timer': timer.stop(start_time)
    }), 200
