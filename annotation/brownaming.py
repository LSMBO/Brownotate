import subprocess
import os

def brownaming(annotation, taxo, output_name, directory_name, custom_db, exclude, max_rank, max_taxo, cpus):
    if os.path.exists(directory_name + "/run_id.txt"):
        with open(directory_name + "/run_id.txt", 'r') as run_id_file:
            resume = run_id_file.readline().strip()
    
        command = f"python ../../Brownaming-1.0.0/main.py --resume {resume}"
        print(command)
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    else:
        taxonID = int(taxo["taxonId"])
        directory_name = os.path.abspath(directory_name)
        output_name = os.path.basename(output_name)
        command = f"python ../../Brownaming-1.0.0/main.py -p \"{annotation}\" -s \"{taxonID}\" -o {output_name} -dir {directory_name} -c {cpus}"
        if custom_db:
            for tax in custom_db:
                command = command + f" -db {tax}"
        if exclude:
            for tax in exclude:
                command = command + f" -e {tax}"
        if max_rank:
            command = command + f" -mr {max_rank}"
        if max_taxo:
            command = command + f" -mt {max_taxo}"
        print(command)
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)