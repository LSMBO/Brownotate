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
        output_files = runPhix(library_type, files, state['run_id'], state['args']['cpus']) 
        for i in range(len(output_files)):
            output_files[i] = os.path.abspath(output_files[i])
        seq["file_name"] = output_files      
    return output_data

        
def runPhix(library_type, file_names, run_id, cpus):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    output_name = getOuputName(file_names)    
    if (library_type == "paired"):
        command = getPairedCommand(file_names, output_name, cpus)
    else:
        library_type = "single"
        command = getSingleCommand(file_names, output_name, cpus)
        
    bowtie_log_path = "seq/bowtie2.log"
    bowtie_log_null = "seq/null"
    print(command)
    with open(bowtie_log_path, 'w') as stderr:
        with open(bowtie_log_null, 'w') as stdout:
            subprocess.run(command, shell=True, check=True, stdout=stdout, stderr=stderr)

    # Clean up
    if os.path.exists("seq/null"):
        os.remove("seq/null")
        
    if run_id in os.path.abspath(file_names[0]):
        os.remove(file_names[0])
        if library_type == "paired":
            os.remove(file_names[1])
    
    if library_type == "paired":
        output_name_1 = output_name.replace("_phix.fastq", "_phix.1.fastq")
        output_name_2 = output_name.replace("_phix.fastq", "_phix.2.fastq")
        return [output_name_1, output_name_2]
    return [output_name]


def getPairedCommand(file_names, output_name, cpus):
    return f"bowtie2 -p {cpus} -x ../../phix/bt2_index_base -1 {file_names[0]} -2 {file_names[1]} --sensitive --un-conc {output_name} --mm -t"

def getSingleCommand(file_names, output_name, cpus):
    return f"bowtie2 -p {cpus} -x ../../phix/bt2_index_base -U {file_names[0]} --sensitive --un {output_name} --mm -t"
       
def getOuputName(file_names):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    file_name = "seq/" + os.path.basename(file_names[0]).replace(".fq.gz", ".fastq.gz").replace(".fq", ".fastq").replace(".fastq", "_phix.fastq")
    return file_name
