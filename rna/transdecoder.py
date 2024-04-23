import subprocess
import os
import shutil
from Bio import SeqIO

def transdecoder(trinity_output):
    trinity_abs_output = os.path.abspath(trinity_output)
    td_dir = "rna/transdecoder"
    if not os.path.exists(td_dir):
        os.makedirs(td_dir)
    run_dir = os.getcwd()
    os.chdir(td_dir)
    longorfs_log = open("LongOrfs.log", "w")
    command = f"TransDecoder.LongOrfs -t {trinity_abs_output}"
    print(command)
    subprocess.run(command, shell=True, check=True, stdout=longorfs_log, stderr=subprocess.STDOUT)
    longorfs_log.close()
    
    predict_log = open("Predict.log", "w")
    command = f"TransDecoder.Predict -t {trinity_abs_output}"
    print(command)
    subprocess.run(command, shell=True, check=True, stdout=predict_log, stderr=subprocess.STDOUT)
    predict_log.close()
    clear()
    os.chdir(run_dir)
    os.rename("rna/transdecoder/Trinity.fasta.transdecoder.pep", "rna/transdecoder/Transdecoder_prediction.faa")
    rename_ids("rna/transdecoder/Transdecoder_prediction.faa")
    return "rna/transdecoder/Transdecoder_prediction.faa"

def clear():
    shutil.rmtree("Trinity.fasta.transdecoder_dir.__checkpoints")
    shutil.rmtree("Trinity.fasta.transdecoder_dir")
    shutil.rmtree("Trinity.fasta.transdecoder_dir.__checkpoints_longorfs")
    files = os.listdir(".")
    for file in files:
        if file.startswith("pipeliner"):
            os.remove(file)
    os.remove("Trinity.fasta.transdecoder.cds")
    os.remove("Trinity.fasta.transdecoder.bed")
    os.remove("Trinity.fasta.transdecoder.gff3")

def rename_ids(transdecoder_file):
    seq_records = []
    count = 0
    with open(transdecoder_file, 'r') as file_handle:
        for seq_record in SeqIO.parse(file_handle, "fasta"):
            count += 1
            new_id = f"transdecoder_predicted_{count}"
            seq_record.id = new_id
            seq_record.description = ""
            if seq_record.seq[-1] == '*':
                seq_record.seq = seq_record.seq[:-1]
            seq_records.append(seq_record)
    with open(transdecoder_file, 'w') as outfile:
        SeqIO.write(seq_records, outfile, "fasta")
    return transdecoder_file
