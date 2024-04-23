import subprocess

def transrate(trinity_assembly, cpus):
    command = f"transrate --assembly {trinity_assembly} --output transrate --threads={cpus}"
    print(command)
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return "transrate/assemblies.csv"

