import os
import shutil
import subprocess
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

augustus_config_path = f"{config['BROWNOTATE_ENV_PATH']}/config"
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"

env = os.environ.copy()
env["AUGUSTUS_CONFIG_PATH"] = augustus_config_path

def remove(file):
    if os.path.exists(file):
        os.remove(file)

def model(genesraw):
    remove_zero_bp_genes(genesraw)
    run_id = os.path.basename(os.getcwd())
    command = f"\nperl {conda_bin_path}/new_species.pl --species={run_id}"
    if os.path.exists(f"{augustus_config_path}/species/{run_id}"):
        shutil.rmtree(f"{augustus_config_path}/species/{run_id}")
    try:
        print(command)
        subprocess.run(command, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error: Exit code not null : {e.returncode}")
        print(f"Standard output : {e.stdout.decode()}")
        print(f"Error output : {e.stderr.decode()}")
        exit()

    cfg_parameter_file = augustus_config_path + "/species/" + run_id + "/" + run_id + "_parameters.cfg"

    bonafide_path = "annotation/bonafide.out"
    bonafide_path_stderr = "annotation/bonafide.err"
    command = f"etraining --species={run_id} {genesraw}"
    print(command)
    with open(bonafide_path, 'w') as stdout:
        with open(bonafide_path_stderr, 'w') as stderr:
            subprocess.run(command, shell=True, check=True, env=env, stdout=stdout, stderr=stderr)

    command = f"grep -c \"Variable stopCodonExcludedFromCDS set right\" annotation/bonafide.err"
    print(command)
    num_stop = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())

    command = f"grep -c LOCUS {genesraw}"
    print(command)
    num_locus = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    if num_stop > num_locus/2:
        change_cfg_stop(cfg_parameter_file)
    
    badlst_path = "annotation/bad.lst"
    badlst_path_stderr = "annotation/bad.lst.err"
    command = f"etraining --species={run_id} {genesraw} 2>&1 | grep \"in sequence\" | perl -pe 's/.*n sequence (\S+):.*/$1/' | sort -u"
    print(command)

    with open(badlst_path, 'w') as stdout:
        with open(badlst_path_stderr, 'w') as stderr:
            subprocess.run(command, shell=True, check=True, env=env, stdout=stdout, stderr=stderr)

    genes_gb_path = "annotation/genes.gb"
    genes_gb_path_stderr = "annotation/genes.gb.err"
    command = f"perl {conda_bin_path}/filterGenes.pl annotation/bad.lst {genesraw} > annotation/genes.gb"
    print(command)

    with open(genes_gb_path, 'w') as stdout:
        with open(genes_gb_path_stderr, 'w') as stderr:
            subprocess.run(command, shell=True, check=True, env=env, stdout=stdout, stderr=stderr)
    
    command = f"grep -c LOCUS annotation/genes.gb"
    print(command)
    num_genes = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())

    remove("annotation/bad.lst")
    remove("annotation/bad.lst.err")
    remove("annotation/bonafide.out")
    remove("annotation/bonafide.err")
    remove("annotation/genes.raw.gb")
    remove("annotation/genes.gb.err")
    return num_genes
    
    
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


