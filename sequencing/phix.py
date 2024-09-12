import subprocess
import os
import copy

def filter_phix_files(sequencing_files, state):
    output_data = copy.deepcopy(sequencing_files)
    for seq in output_data:
        library_type="paired"
        if len(seq["file_name"])==1:
            library_type="single"
        files = seq["file_name"]
        print("runPhix with ", files)
        output_files = runPhix(library_type, files, state['run_id']) 
        for i in range(len(output_files)):
            output_files[i] = os.path.abspath(output_files[i])
        seq["file_name"] = output_files      
    return output_data

        
def runPhix(library_type, file_name, run_id):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    if (library_type == "paired"):
        output_names = getPairedOuputName(file_name)
        command = getPairedCommand(file_name)
    else:
        library_type = "single"
        output_names = getSingleOuputName(file_name)
        command = getSingleCommand(file_name)
        
    bowtie_log_path = "seq/bowtie2.log"
    bowtie_log_null = "seq/null"
    print(command)
    with open(bowtie_log_path, 'w') as stderr:
        with open(bowtie_log_null, 'w') as stdout:
            subprocess.run(command, shell=True, check=True, stdout=stdout, stderr=stderr)

    clean(output_names)
    if run_id in os.path.abspath(file_name[0]):
        os.remove(file_name[0])
        if library_type == "paired":
            os.remove(file_name[1])
    return output_names


def getPairedCommand(file_name):
    return f"bowtie2 -p 12 -x ../../phix/bt2_index_base -1 {file_name[0]} -2 {file_name[1]} --sensitive --un-conc-gz seq/unmapped_phix.fastq.gz"

def getSingleCommand(file_name):
    return f"bowtie2 -p 12 -x ../../phix/bt2_index_base -U {file_name[0]} --sensitive --un-gz seq/unmapped_phix.fastq.gz"

def getPairedOuputName(file_name):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    file1 = "seq/" + os.path.basename(file_name[0].replace(".fq", ".fastq"))
    file2 = "seq/" + os.path.basename(file_name[1].replace(".fq", ".fastq"))
    return [file1.replace(".fastq.gz", "_phix.fastq.gz"), file2.replace(".fastq.gz", "_phix.fastq.gz")]
       
def getSingleOuputName(file_name):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    file_name = "seq/" + os.path.basename(file_name[0].replace(".fq", ".fastq"))
    return [file_name.replace(".fastq.gz", "_phix.fastq.gz")]

def clean(output_names):
    for f in os.listdir("seq"):
        if f == "null":
            os.remove("seq/"+f)
        if f == "unmapped_phix.fastq.1.gz":
            os.rename("seq/"+f, output_names[0])
        if f == "unmapped_phix.fastq.2.gz":
            os.rename("seq/"+f, output_names[1])
        if f == "unmapped_phix.fastq.gz":
            os.rename("seq/"+f, output_names[0])
