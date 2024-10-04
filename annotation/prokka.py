import os
import shutil
import subprocess

def prokka(genome, cpus):
    if os.path.exists("annotation"):
        shutil.rmtree("annotation")
    
    command = f"prokka --outdir annotation --prefix prokka_annotation --cpus {cpus} --noanno --norrna --notrna {genome}"
    print(command)
    
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Change ownership of files to current user
    change_owner_recursive("annotation")

    clear()
    
    return "annotation/prokka_annotation.faa"

def clear():
    files = os.listdir("annotation")
    for file in files:
        if file != "prokka_annotation.faa":
            os.remove("annotation/" + file)

def change_owner_recursive(directory):
    user_uid = os.getuid()
    user_gid = os.getgid()

    for root, dirs, files in os.walk(directory):
        os.chown(root, user_uid, user_gid)
        for dir in dirs:
            os.chown(os.path.join(root, dir), user_uid, user_gid)
        for file in files:
            os.chown(os.path.join(root, file), user_uid, user_gid)
