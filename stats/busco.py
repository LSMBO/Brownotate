import shutil
import os
import subprocess
import json
import csv

def busco(input_file, taxo, mode, cpus, busco_lineage_dirpath="../../stats/", custom=False, ):
    if not busco_lineage_dirpath.endswith('/'):
        busco_lineage_dirpath = busco_lineage_dirpath + '/'
    busco_lineage = busco_lineage_dirpath + "eukaryota_odb10"
    lineage = taxo["lineage"]
    for entry in lineage:
        group = entry["taxonId"]
        if group == 2:
            busco_lineage = busco_lineage_dirpath + "bacteria_odb10"
        if group == 2157:
            busco_lineage = busco_lineage_dirpath + "archaea_odb10"
    output_rep = "busco_genome"
    if custom:
        output_rep = "busco_custom_genome"
    if mode == "proteins":
        output_rep = "busco_annotation"
        if custom:
            output_rep = "busco_custom_annotation"
    command = get_command(cpus, input_file, busco_lineage, output_rep, mode)
    with open('log_bin', 'w') as log_bin:
        print(command)
        subprocess.run(command, shell=True, check=True, stdout=log_bin, stderr=subprocess.PIPE)
    if os.path.exists("busco_downloads"):
        shutil.rmtree("busco_downloads")
    if os.path.exists("log_bin"):
        os.remove("log_bin")
    result = get_busco_result(output_rep)
    for directory in ["run_bacteria_odb10", "run_eukaryota_odb10", "run_archaea_odb10"]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
    if mode=='genome':
        makeJson("Busco_genome.json", result)
    else:
        makeJson("Busco_annotation.json", result)
    
    return result

def makeJson(title, object):
    with open(title, "w") as f:
        json.dump(object, f)


def get_command(cpus, input_file, lineage, output_rep, mode):
    return f"busco -c {cpus} -i {input_file} -l {lineage} -o {output_rep} -m {mode} --offline"

def get_full_table_path(output_rep):
    run_directories = ["run_bacteria_odb10", "run_eukaryota_odb10", "run_archaea_odb10"]
    for directory in run_directories:
        file_path = os.path.join(output_rep, directory, "full_table.tsv")
        if os.path.exists(file_path):
            return file_path
        
def get_busco_result(output_rep):
    result = {}
    for file in os.listdir(output_rep):
        if file.endswith(".json"):
            with open(output_rep+"/"+file) as f:
                result = json.load(f)
    full_table_path = get_full_table_path(output_rep)
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