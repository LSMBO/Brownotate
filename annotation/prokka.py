import subprocess
import os
import shutil

def prokka(genome, cpus):
    if os.path.exists("annotation"):
        shutil.rmtree("annotation")
    command = f"prokka --outdir annotation --proteins FASTA --prefix prokka_annotation --cpus {cpus} {genome}"
    print(command)
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    clear()
    
    return "annotation/prokka_annotation.faa"

def clear():
    files = os.listdir("annotation")
    for file in files:
        if file != "prokka_annotation.faa":
            os.remove("annotation/"+file)
