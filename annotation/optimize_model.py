import subprocess
import os
import re

conda_prefix = os.environ["CONDA_PREFIX"]
augustus_config_path = conda_prefix + "/config"
conda_bin_path = conda_prefix + "/bin"
env = os.environ.copy()
env["AUGUSTUS_CONFIG_PATH"] = augustus_config_path

def optimize_model(num_genes):
    genes_file = "annotation/genes.gb"
    run_id = os.path.basename(os.getcwd())
    if num_genes > 5000:
        command = f"{conda_bin_path}/randomSplit.pl {genes_file} 5000"
        print(command)
        subprocess.run(command, shell=True, check=True, env=env)
        genes_file = "annotation/genes.gb.train"
    command = f"{conda_bin_path}/optimize_augustus.pl --species={run_id} --cpus=12 --kfold=8 --onlytrain {genes_file}"
    print(command)
    subprocess.run(command, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    command = f"etraining --species={run_id} {genes_file} &> annotation/etrain.out"
    try:
        print(command)
        subprocess.run(command, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"Error: Exit code not null : {e.returncode}")
        print(f"Standard output : {e.stdout.decode()}")
        print(f"Error output : {e.stderr.decode()}")
        exit()
    tag, taa, tga = get_stop_proba("annotation/etrain.out")
    cfg_parameter_file = augustus_config_path + "/species/" + run_id + "/" + run_id + "_parameters.cfg"
    change_cfg_stop_prob(cfg_parameter_file, tag, taa, tga)
    clean()

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

def clean():
    os.remove("annotation/etrain.out")
    os.remove("annotation/genes.gb")