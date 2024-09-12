import subprocess
import os
import multiprocessing
import shutil
from Bio import SeqIO
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"

work_dir = f"annotation/augustus_work_dir"

def augustus(genome_files):
    run_id = os.path.basename(os.getcwd())
    os.makedirs(work_dir, exist_ok=True)
    os.chdir(work_dir)
    
    with multiprocessing.Pool() as pool:
        results = []
        for i, genome_file in enumerate(genome_files):
            output_name = f"augustus_part{i+1}"
            genome_file = os.path.basename(genome_file)
            result = pool.apply_async(run_augustus, args=(genome_file, output_name, run_id))
            results.append(result)
 
        annotation_files = []
        for result in results:
            annotation_files.append(result.get())
        augustus_annotation = concatenate_files(annotation_files)
        clean(genome_files)
        return augustus_annotation
    
def run_augustus(genome_file, output_name, run_id):
    output_aa_file = f"{output_name}.aa"
    output_gff_file = f"{output_name}.gff"
    if not os.path.exists(output_aa_file):
        command = f"augustus --species={run_id} ../{genome_file} > {output_gff_file}"
        print(command)
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        command = f"perl {conda_bin_path}/getAnnoFasta.pl {output_name}.gff"
        print(command)
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_aa_file
              
def concatenate_files(annotation_files):
    seq_records = []
    count = 0
    for file in annotation_files:
        if os.path.exists(file):
            with open(file, 'r') as file_handle:
                for seq_record in SeqIO.parse(file_handle, "fasta"):
                    count += 1
                    new_id = f"augustus_predicted_{count}"
                    seq_record.id = new_id
                    seq_record.description = ""
                    seq_records.append(seq_record)
    with open("../augustus_annotation.faa", 'w') as outfile:
        SeqIO.write(seq_records, outfile, "fasta")
    return "annotation/augustus_annotation.faa"

def clean(genome_files):
    augustus_wd = os.getcwd()
    parent_dir1 = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    os.chdir(parent_dir1)
    parent_dir2 = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    os.chdir(parent_dir2)
    shutil.rmtree(augustus_wd)
    for file in genome_files:
        os.remove(file)

        