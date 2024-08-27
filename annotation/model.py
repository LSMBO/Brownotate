import os
import shutil
import subprocess

conda_prefix = os.environ["CONDA_PREFIX"]
augustus_config_path = conda_prefix + "/config"
conda_bin_path = conda_prefix + "/bin"
env = os.environ.copy()
env["AUGUSTUS_CONFIG_PATH"] = augustus_config_path

def model(genesraw):
    remove_zero_bp_genes(genesraw)
    run_id = os.path.basename(os.getcwd())
    command = f"{conda_bin_path}/new_species.pl --species={run_id}"
    if os.path.exists(f"{augustus_config_path}/species/{run_id}"):
        shutil.rmtree(f"{augustus_config_path}/species/{run_id}")
    try:
        subprocess.run(command, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error: Exit code not null : {e.returncode}")
        print(f"Standard output : {e.stdout.decode()}")
        print(f"Error output : {e.stderr.decode()}")
        exit()
    
    cfg_parameter_file = augustus_config_path + "/species/" + run_id + "/" + run_id + "_parameters.cfg"
    command = f"etraining --species={run_id} {genesraw} &> annotation/bonafide.out"
    print(command)
    subprocess.run(command, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    command = f"grep -c \"Variable stopCodonExcludedFromCDS set right\" annotation/bonafide.out"
    print(command)
    num_stop = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    print(command)
    command = f"grep -c LOCUS {genesraw}"
    num_locus = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    if num_stop > num_locus/2:
        change_cfg_stop(cfg_parameter_file)
    command = f"etraining --species={run_id} {genesraw} 2>&1 | grep \"in sequence\" | perl -pe 's/.*n sequence (\S+):.*/$1/' | sort -u > annotation/bad.lst"
    print(command)
    subprocess.run(command, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    command = f"{conda_bin_path}/filterGenes.pl annotation/bad.lst {genesraw} > annotation/genes.gb"
    print(command)
    subprocess.run(command, shell=True, check=True, env=env)
    command = f"grep -c LOCUS annotation/genes.gb"
    print(command)
    num_genes = int(subprocess.run(command, stdout=subprocess.PIPE, shell=True).stdout.decode().strip())
    clean()
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

def clean():
    os.remove("annotation/bad.lst")
    os.remove("annotation/bonafide.out")
    os.remove("annotation/genes.raw.gb")