import subprocess
import os
import copy

def filter_fastp_files(state):
    output_data = copy.deepcopy(state["dnaseq_files"])
    for seq in output_data:
        if "PACBIO" in seq["platform"]:
            continue
        library_type="paired"
        if len(seq["file_name"])==1:
            library_type="single"
        output_files = runFastp(library_type, seq["file_name"], state['run_id'], state['args']['cpus'])            
        for i in range(len(output_files)):
            output_files[i] = os.path.abspath(output_files[i])
        seq["file_name"] = output_files
    return output_data
   
def runFastp(library_type, file_name, run_id, cpus):
    if (library_type == "paired"):
        output_name = getPairedOuputName(file_name)
        command = getPairedCommand(file_name, output_name, cpus)
    else:
        output_name = getSingleOuputName(file_name)
        command = getSingleCommand(file_name, output_name, cpus)

    print(f'\n{command}')
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run_id in os.path.abspath(file_name[0]):
        os.remove(file_name[0])
        if library_type == "paired":
            os.remove(file_name[1])
    return output_name


def getPairedCommand(file_name, output_name, cpus):
    return f"fastp -i {file_name[0]} -w {cpus} -I {file_name[1]} -o {output_name[0]} -O {output_name[1]} -j seq/fastp/fastp_log.json -h seq/fastp/fastp_log.html --dont_eval_duplication"

def getSingleCommand(file_name, output_name, cpus):
    return f"fastp -i {file_name[0]} -w {cpus} -o {output_name[0]} -j seq/fastp/fastp_log.json -h seq/fastp/fastp_log.html --dont_eval_duplication"

def getPairedOuputName(file_name):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    file1 = "seq/" + os.path.basename(file_name[0].replace(".fq", ".fastq"))
    file2 = "seq/" + os.path.basename(file_name[1].replace(".fq", ".fastq"))
    return [file1.replace(".fastq", "_fastp.fastq"), file2.replace(".fastq", "_fastp.fastq")]

def getSingleOuputName(file_name):
    if not os.path.exists("seq"):
        os.makedirs("seq")
    file_name = "seq/" + os.path.basename(file_name[0].replace(".fq", ".fastq"))
    return [file_name.replace(".fastq", "_fastp.fastq")]





