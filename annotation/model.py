import subprocess
import os
import shutil
import json
import re
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
import shutil
from flask_app.commands import run_command

run_model_bp = Blueprint('run_model_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
augustus_config_path = f"{config['BROWNOTATE_ENV_PATH']}/config"
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"
env["AUGUSTUS_CONFIG_PATH"] = augustus_config_path

@run_model_bp.route('/run_model', methods=['POST'])
def run_model():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    genesraw = request.json.get('genesraw')
    wd = parameters['id']

    remove_zero_bp_genes(genesraw)
    command = f"\nperl {conda_bin_path}/new_species.pl --species={wd}"
    if os.path.exists(f"{augustus_config_path}/species/{wd}"):
        shutil.rmtree(f"{augustus_config_path}/species/{wd}")
    
    stdout, stderr, returncode = run_command(command, wd, env=env)
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'new_species.pl command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    

    cfg_parameter_file = f"{augustus_config_path}/species/{wd}/{wd}_parameters.cfg"

    bonafide_stdout_path = f"runs/{wd}/annotation/bonafide.out"
    bonafide_stderr_path = f"runs/{wd}/annotation/bonafide.err"
    command = f"etraining --species={wd} {genesraw}"
    
    stdout, stderr, returncode = run_command(command, wd, stdout_path=bonafide_stdout_path, stderr_path=bonafide_stderr_path, env=env)
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'etraining command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    

    # By default the gene model considers that genes end with a stop codon (stopCodonExcludedFromCDS=false). 
    # If more than 50% of the genes (from genes.raw.gb) do not end with a stop codon (in bonafide.err), we change the parameter in the configuration file.
    command = f"grep -c \"Variable stopCodonExcludedFromCDS set right\" {bonafide_stderr_path}"
    num_genes_without_stop_codon = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip()) # Number of genes not ending with a stop codon

    command = f"grep -c LOCUS {genesraw}"
    num_locus = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    
    if num_genes_without_stop_codon > num_locus/2:
        print(f"More than 50% of the genes do not end with a stop codon ({num_genes_without_stop_codon}>({num_locus}/2)). Changing the parameter stopCodonExcludedFromCDS to true in {cfg_parameter_file}")
        change_cfg_stop(cfg_parameter_file)
        
        command = f"etraining --species={wd} {genesraw}" # Re-run etraining after changing the parameter
        stdout, stderr, returncode = run_command(command, wd, stdout_path=bonafide_stdout_path, stderr_path=bonafide_stderr_path, env=env)
        if returncode != 0:          
            return jsonify({
                'status': 'error',
                'message': f'etraining command failed',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 500
    
    badlst_path = f"runs/{wd}/annotation/bad.lst"
    temp_path2 = f"runs/{wd}/annotation/bad_temp2.txt"
    
    try:
        if not os.path.exists(bonafide_stderr_path):
            print(f"ERROR: {bonafide_stderr_path} does not exist")
            with open(badlst_path, 'w') as f:
                f.write("")
        else:
            pattern = re.compile(r'.*in sequence (\S+): .*')
            sequences = set()
            
            with open(bonafide_stderr_path, 'r') as infile:
                try:
                    for line in infile:
                        match = pattern.match(line)
                        if match:
                            sequences.add(match.group(1))
                except Exception as e:
                    print(f"Error during file reading: {str(e)}")
            
            with open(badlst_path, 'w') as outfile:
                for seq in sorted(sequences):
                    outfile.write(f"{seq}\n")
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error during problematic sequence processing',
            'stderr': str(e),
            'timer': timer.stop(start_time)
        }), 500

    genes_gb_path = f"runs/{wd}/annotation/genes.gb"
    genes_gb_path_stderr = f"runs/{wd}/annotation/genes.gb.err"
    
    command = f"perl {conda_bin_path}/filterGenes.pl {badlst_path} {genesraw}" # Filter out bad genes from genes.raw.gb
    stdout, stderr, returncode = run_command(command, wd, stdout_path=genes_gb_path, stderr_path=genes_gb_path_stderr, env=env)
    if returncode != 0:
        return jsonify({
            'status': 'error',
            'message': f'filterGenes command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500

    command = f"grep -c LOCUS runs/{wd}/annotation/genes.raw.gb"
    num_genes_raw = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    print(f"Number of genes genes.raw.gb: {num_genes_raw}")
    
    command = f"grep -c LOCUS runs/{wd}/annotation/genes.gb"
    num_genes = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    print(f"Number of genes genes.gb: {num_genes}")
          
    return jsonify({
        'status': 'success', 
        'data': num_genes, 
        'timer': timer.stop(start_time)
    }), 200
    
def change_cfg_stop(cfg_parameter_file):
    with open(cfg_parameter_file, "r") as file:
        lines = file.readlines()
    with open(cfg_parameter_file, "w") as file:
        for line in lines:
            if line.startswith("stopCodonExcludedFromCDS false"):
                line = line.replace("stopCodonExcludedFromCDS false", "stopCodonExcludedFromCDS true")
            file.write(line)

def remove_zero_bp_genes(genesraw):
    cpt = 0
    with open(genesraw, 'r') as genesrawgb:
        lines = genesrawgb.readlines()
    with open(genesraw, 'w') as genesraw:
        for i, line in enumerate(lines):
            if line.endswith(" 0 bp  DNA\n") and lines[i-1].startswith("LOCUS"):
                cpt = cpt + 1 
                continue
            genesraw.write(line)
    return cpt


