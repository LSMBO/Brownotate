import subprocess
import os
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

def run_command(cmd, env):
    retry_count = 0
    success = False
    while retry_count < 5 and not success:
        try:
            print(cmd)
            subprocess.run(cmd, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            success = True
        except subprocess.CalledProcessError as e:
            retry_count += 1
            
    if not success:
        print("Failed to download sequencing data after 5 attempts.")
        return None
    return True


def download_sra(data, cpus):
    commands = []
    env = os.environ.copy()
    env['PATH'] = os.path.join(config['SRA_DOWNLOAD_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
    fastq_files = []
    for run_data in data["runs"]:
        accession = run_data["accession"]
        platform = run_data["platform"]
        library_type = run_data["library_type"]
        
        prefetch_cmd = f"prefetch {accession} -o seq/{accession}.sra --max-size 1500G"            
        if run_command(prefetch_cmd, env):

            if platform in ["ILLUMINA", "ION_TORRENT", "454", "BGISEQ", "OXFORD_NANOPORE", "PACBIO_SMRT"]:
                if library_type == "paired":
                    fasterqdump_cmd = f"fasterq-dump seq/{accession}.sra --outdir seq --skip-technical --split-files"
                else:
                    fasterqdump_cmd = f"fasterq-dump seq/{accession}.sra --outdir seq --skip-technical"
                if run_command(fasterqdump_cmd, env):
                    if library_type == "paired":
                        fastq_files.append({
                            "accession": accession, 
                            "file_name": [f"seq/{accession}_1.fastq", f"seq/{accession}_2.fastq"], 
                            "platform": platform
                        })
                    else:
                        fastq_files.append({"accession": accession, "file_name": f"seq/{accession}.fastq", "platform": platform})
                else:
                    print(f"Error: The sequencing data for {accession} could not be downloaded properly. Passing...") 
            else:
                print(f"Error: The platform {platform} is not supported for the sequencing {accession}")

    return fastq_files
