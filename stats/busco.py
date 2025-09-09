import shutil
import os, sys
import json
import csv
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command

run_busco_bp = Blueprint('run_busco_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

@run_busco_bp.route('/run_busco', methods=['POST'])
def run_busco():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    mode = request.json.get('mode')
    input_file = request.json.get('input_file')
    taxo = parameters['species']

    output_rep = f"runs/{wd}/busco_genome"
    if mode == "proteins":
        output_rep = f"runs/{wd}/busco_annotation"

    if os.path.exists(output_rep):
        shutil.rmtree(output_rep)
        
    busco_lineage = get_busco_lineage(taxo)
    if os.path.exists(f"stats/{busco_lineage}"):
        busco_lineage_path = f"stats/{busco_lineage}"
        command = get_command(cpus, input_file, output_rep, mode, busco_lineage_path, True, wd)
    else:
        command = get_command(cpus, input_file, output_rep, mode, busco_lineage, False, wd) 

    stdout, stderr, returncode = run_command(command, wd, cpus=cpus, stdout_path=f"runs/{wd}/log_bin")
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'Busco command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    

    lineage_dir = f"runs/{wd}/busco_downloads/lineages/{busco_lineage}"
    if os.path.exists(lineage_dir):
        shutil.move(lineage_dir, f"stats/{busco_lineage}")
        
    if os.path.exists(f"runs/{wd}/busco_downloads"):
        shutil.rmtree(f"runs/{wd}/busco_downloads")
    if os.path.exists(f"runs/{wd}/log_bin"):
        os.remove(f"runs/{wd}/log_bin")
        
    result = get_busco_result(output_rep, busco_lineage)
    
    if os.path.exists(f"run_{busco_lineage}"):
        shutil.rmtree(f"run_{busco_lineage}")

    if mode=='genome':    
        make_json(f"runs/{wd}/Busco_genome.json", result)
        
    else:
        make_json(f"runs/{wd}/Busco_annotation.json", result)

    return jsonify({
        'status': 'success', 
        'data': result, 
        'timer': timer.stop(start_time)
    }), 200

def make_json(title, object):
    with open(title, "w") as f:
        json.dump(object, f)

def get_busco_lineage(taxo):
    lineage_names = [entry['scientificName'].lower() for entry in taxo['lineage']]

    with open("stats/busco_lineages.txt", 'r') as lineages_file:
        lines = lineages_file.readlines()
        
    lineage_tree = {}
    current_level = [lineage_tree]

    for line in lines:
        level = line.count('    ')
        lineage_name = line.strip()
        current_level = current_level[:level + 1]
        current_level[-1][lineage_name] = {}
        current_level.append(current_level[-1][lineage_name])

    def search_best_lineage(tree, names, last_key=None):
        for name in names:
            name_with_suffix = f"{name}_odb10"
            if name_with_suffix in tree:
                return search_best_lineage(tree[name_with_suffix], names, name_with_suffix)
        return last_key
    
    return search_best_lineage(lineage_tree, lineage_names)

def get_command(cpus, input_file, output_rep, mode, lineage, offline, wd):
    download_path = f"runs/{wd}/busco_downloads"
    base_cmd = f"busco -c {cpus} -i {input_file} -o {output_rep} -m {mode} -l {lineage} --out_path runs/{wd} --download_path {download_path} --metaeuk"
    if offline:
        return base_cmd + " --offline"
    return base_cmd

def get_full_table_path(output_rep, lineage):
    file_path = os.path.join(output_rep, f"run_{lineage}/full_table.tsv")
    if os.path.exists(file_path):
        return file_path

def get_busco_result(output_rep, lineage):
    result = {}
    for file in os.listdir(output_rep):
        if file.endswith(".json"):
            with open(output_rep+"/"+file) as f:
                result = json.load(f)
    full_table_path = get_full_table_path(output_rep, lineage)
    if full_table_path:
        with open(full_table_path, newline='') as tsvfile:
            next(tsvfile)
            next(tsvfile)
            header = next(tsvfile).strip().split('\t')
            reader = csv.DictReader(tsvfile, delimiter='\t', fieldnames=header)
            completed = []
            fragmented = []
            duplicated = []
            missing = []
            for row in reader:
                if row["Status"] == 'Complete':
                    completed.append(row["# Busco id"])
                elif row["Status"] == 'Fragmented':
                    fragmented.append(row["# Busco id"])
                elif row["Status"] == 'Duplicated':
                    duplicated.append(row["# Busco id"])
                elif row["Status"] == 'Missing':
                    missing.append(row["# Busco id"])
            full_table_result = {
                "completed": completed,
                "fragmented": fragmented,
                "duplicated": duplicated,
                "missing": missing
            }
            result["full_table"] = full_table_result
    return result

