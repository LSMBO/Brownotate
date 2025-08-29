import os
import re
import json
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command
import shutil


run_optimize_model_bp = Blueprint('run_optimize_model_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
augustus_config_path = f"{config['BROWNOTATE_ENV_PATH']}/config"
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"
env["AUGUSTUS_CONFIG_PATH"] = augustus_config_path

@run_optimize_model_bp.route('/run_optimize_model', methods=['POST'])
def run_optimize_model():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    num_genes = request.json.get('num_genes')
    wd = parameters['id']
    cpus = parameters['cpus']
    
    genes_file = f"runs/{wd}/annotation/genes.gb"
    
    if num_genes > 300:
        command = f"perl {conda_bin_path}/randomSplit.pl {genes_file} 300"
        stdout, stderr, returncode = run_command(command, wd)
        if returncode != 0:          
            return jsonify({
                'status': 'error',
                'message': f'randomSplit.pl command failed',
                'command': command,
                'stderr': stderr,
                'stdout': stdout,
                'timer': timer.stop(start_time)
            }), 500    

        train_genes_file = "genes.gb.train"
        test_genes_file = "genes.gb.test"
        command = f"perl {conda_bin_path}/optimize_augustus.pl --species={wd} --cpus={cpus} --kfold={cpus} --cleanup=1 --onlytrain={train_genes_file} {test_genes_file}"
    else:
        command = f"perl {conda_bin_path}/optimize_augustus.pl --species={wd} --cpus={cpus} --kfold={cpus} --cleanup=1 {os.path.basename(genes_file)}"
    
    os.chdir(f"runs/{wd}/annotation")
    stdout, stderr, returncode = run_command(command, wd, cpus=cpus, stdout_path="optimize.out", env=env)
    os.chdir(f"../../..")
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'optimize_augustus.pl command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    
    
    etrain_path = f"runs/{wd}/annotation/etrain.out"
    
    etrain_out = f"runs/{wd}/annotation/etrain.out"
    etrain_err = f"runs/{wd}/annotation/etrain.err"
    command = f"etraining --species={wd} --stopCodonExcludedFromCDS=true {genes_file}"
    stdout, stderr, returncode = run_command(command, wd, stdout_path=etrain_out, stderr_path=etrain_err)
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'etraining command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    
    
    tag, taa, tga = get_stop_proba(etrain_path)
    print(f"Extracted stop codon probabilities: tag={tag}, taa={taa}, tga={tga}")
    cfg_parameter_file = f"{augustus_config_path}/species/{wd}/{wd}_parameters.cfg"
    change_cfg_stop_prob(cfg_parameter_file, tag, taa, tga)
    # clean(wd)
    
    return jsonify({
        'status': 'success', 
        'timer': timer.stop(start_time)
    }), 200

def get_stop_proba(etrainout_file):
    with open(etrainout_file, "r") as file:
        lines = file.readlines()
    tag = None
    taa = None
    tga = None
    for line in reversed(lines):
        if "tag" in line:
            tag = line.strip().split()[-1].strip("()")
        elif "taa" in line:
            taa = line.strip().split()[-1].strip("()")
        elif "tga" in line:
            tga = line.strip().split()[-1].strip("()")
        if tag and taa and tga:
            break
    return tag, taa, tga

def change_cfg_stop_prob(cfg_parameter_file, tag, taa, tga):
    with open(cfg_parameter_file, "r") as file:
        lines = file.readlines()
    with open(cfg_parameter_file, "w") as file:
        for line in lines:
            if re.match(r"^/Constant/amberprob( ){19}.+", line):
                line = f"/Constant/amberprob                   {tag}   # Prob(stop codon = tag)\n"
            elif re.match(r"^/Constant/ochreprob( ){19}.+", line):
                line = f"/Constant/ochreprob                   {taa}   # Prob(stop codon = taa)\n"
            elif re.match(r"^/Constant/opalprob( ){20}.+", line):
                line = f"/Constant/opalprob                    {tga}   # Prob(stop codon = tga)\n"
            file.write(line)

def clean(wd):
    os.remove(f"runs/{wd}/annotation/etrain.out")
    os.remove(f"runs/{wd}/annotation/genes.gb")