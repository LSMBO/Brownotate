import subprocess
import os
import shutil

conda_prefix = os.environ["CONDA_PREFIX"] + "/bin"

def trinity(rnaseq, threads):
    if not os.path.exists("rna"):
        os.makedirs("rna")
        
    if not os.path.exists("rna/trinity"):
        os.makedirs("rna/trinity")

    command = f"{conda_prefix}/perl {conda_prefix}/Trinity --seqType fq --max_memory 200G --CPU {threads} --no_version_check --no_bowtie --output rna/trinity"
    cmd_forward = ""
    cmd_reverse = ""
    cmd_single = ""
    f = ""
    r = ""
    s = ""
    
    for seq in rnaseq:
        library_type="paired"
        if len(seq["file_name"])==1:
            library_type="single"
            
        files = seq["file_name"]
        if "phix_file_name" in seq:
            files = seq["phix_file_name"]
        elif "fastp_file_name" in seq:
            files = seq["fastp_file_name"]

        if library_type=="paired":
            f = f + files[0]+","
            r = r + files[1]+","
        else:
            s = s + files[0]+","
            
    if f != "":
        cmd_forward = " --left "
        cmd_reverse = " --right "
        f = f[:-1]
        r = r[:-1]
    if s != "":
        cmd_single = " --single "
        s = s[:-1] 
        
    command = command + cmd_forward + f + cmd_reverse + r + cmd_single + s

    print(command)
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    clear()
    return "rna/trinity/Trinity.fasta"

def clear():
    trin_dir = "rna/trinity"
    run_dir = os.getcwd()
    os.chdir(trin_dir)
    shutil.rmtree("chrysalis")
    shutil.rmtree("read_partitions")
    files = os.listdir(".")
    for file in files:
        if file != "Trinity.fasta" and file != "Trinity.timing":
            os.remove(file)
    
    os.chdir(run_dir)