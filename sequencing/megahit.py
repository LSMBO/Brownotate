import subprocess
import os
import shutil

def megahit(scientific_name, sequencing_files, cpus, run_id):
    output_name = "genome/" + scientific_name.replace(' ','_') + "_Megahit.fasta"
    single_seq_files = []
    paired_fwd_seq_files = []
    paired_rev_seq_files = []
    for seq in sequencing_files:
        library_type="paired"
        if len(seq["file_name"])==1:
            library_type="single"
        files = seq["file_name"]

        if library_type == "single":
            single_seq_files.append(files[0])
        else:
            paired_fwd_seq_files.append(files[0])
            paired_rev_seq_files.append(files[1])

    command_part1 = f"megahit -o genome/megahit_working_dir -t {cpus} --mem-flag 2 -m 0.9 "
    command_part_single = ""
    if len(single_seq_files)!=0:
        command_part_single = "-r "+','.join(single_seq_files)+" "
        
    command_part_paired_forward = ""
    command_part_paired_reverse = ""
    if len(paired_fwd_seq_files)!=0:
        command_part_paired_forward = "-1 "+','.join(paired_fwd_seq_files)+" "
        command_part_paired_reverse = "-2 "+','.join(paired_rev_seq_files)+" "
    
    command = command_part1 + command_part_single + command_part_paired_forward + command_part_paired_reverse
    if not os.path.exists("genome"):
        os.makedirs("genome")
    if os.path.exists("genome/megahit_working_dir"):
        shutil.rmtree("genome/megahit_working_dir")    
    print(command)
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists("genome/megahit_working_dir/final.contigs.fa"):
        os.rename("genome/megahit_working_dir/final.contigs.fa", output_name)
        os.rename("genome/megahit_working_dir/log", "genome/megahit.log")
        shutil.rmtree("genome/megahit_working_dir")
    
    for seq in sequencing_files:
        for file in seq["file_name"]:
            if run_id in os.path.abspath(file):
                os.remove(file)
            
    return os.path.abspath(output_name)
