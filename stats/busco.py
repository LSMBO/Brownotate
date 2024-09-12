import shutil
import os, sys
import subprocess
import json
import csv

def busco(input_file, taxo, mode, cpus, custom=False):
    output_rep = "busco_genome"
    if custom:
        output_rep = "busco_custom_genome"
    if mode == "proteins":
        output_rep = "busco_annotation"
        if custom:
            output_rep = "busco_custom_annotation"
    if os.path.exists(output_rep):
        shutil.rmtree(output_rep)
        
    busco_lineage = get_busco_lineage(taxo)
    if os.path.exists(f"../../stats/{busco_lineage}"):
        busco_lineage_path = f"../../stats/{busco_lineage}"
        command = get_command(cpus, input_file, output_rep, mode, busco_lineage_path, True)
    else:
        command = get_command(cpus, input_file, output_rep, mode, busco_lineage, False)     
    
    print(command)
    with open('log_bin', 'w') as log_bin:
        process = subprocess.run(command, shell=True, check=True, stdout=log_bin, stderr=subprocess.PIPE, text=True)
        if process.stderr:
            print("Error: ", process.stderr)
    
    lineage_dir = f"busco_downloads/lineages/{busco_lineage}"
    if os.path.exists(lineage_dir):
        shutil.move(lineage_dir, f"../../stats/{busco_lineage}")
        
    if os.path.exists("busco_downloads"):
        shutil.rmtree("busco_downloads")
    if os.path.exists("log_bin"):
        os.remove("log_bin")
        
    result = get_busco_result(output_rep, busco_lineage)
    
    if os.path.exists(f"run_{busco_lineage}"):
        shutil.rmtree(f"run_{busco_lineage}")

    if mode=='genome':
        makeJson("Busco_genome.json", result)
    else:
        makeJson("Busco_annotation.json", result)
    
    return result

def makeJson(title, object):
    with open(title, "w") as f:
        json.dump(object, f)

def get_busco_lineage(taxo):
    lineage_names = [entry['scientificName'].lower() for entry in taxo['lineage']]

    with open("../../stats/busco_lineages.txt", 'r') as lineages_file:
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

def get_command(cpus, input_file, output_rep, mode, lineage, offline):
    if offline:
        return f"busco -c {cpus} -i {input_file} -o {output_rep} -m {mode} -l {lineage} --metaeuk --offline"
    return f"busco -c {cpus} -i {input_file} -o {output_rep} -m {mode} -l {lineage} --metaeuk"

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

