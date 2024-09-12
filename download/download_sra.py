import subprocess
import os
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, '..', 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

def download_sra(data):
    commands = []
    sra_files = []

    for run_data in data["runs"]:
        accession = run_data["accession"]
        platform = run_data["platform"]
        library_type = run_data["library_type"]

        if platform == "ILLUMINA" or platform == "ION_TORRENT" or platform == "454" or platform == 'BGISEQ' or platform == 'OXFORD_NANOPORE' or platform == "PACBIO_SMRT":
            if library_type == "paired":
                cmd = f"fastq-dump --split-files --outdir seq --gzip --skip-technical --readids --clip --accession {accession}"
            else:
                cmd = f"fastq-dump --outdir seq --gzip --skip-technical --readids --clip --accession {accession}"
            
            command = {}
            command["cmd"] = cmd
            command["accession"] = accession
            command["library_type"] = library_type
            command["platform"] = platform
            if library_type == "paired":
                command["file_name"] = [f"seq/{accession}_1.fastq.gz", f"seq/{accession}_2.fastq.gz"]
            else:
                command["file_name"] = [f"seq/{accession}.fastq.gz"]
            commands.append(command)
        else:
            print(f"Error : The platform {platform} is not supported for the sequencing {accession}")
    
    for command in commands:
        cmd = command["cmd"]
        accession = command["accession"]
        library_type = command["library_type"]
        
        retry_count = 0
        success = False
        
        env = os.environ.copy()
        env['PATH'] = os.path.join(config['SRA_DOWNLOAD_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

        while retry_count < 5 and not success:
            try:
                print(cmd)
                subprocess.run(cmd, shell=True, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                success = True
            except subprocess.CalledProcessError as e:
                retry_count += 1
                # Delete partially downloaded files
                if library_type == "paired":
                    if os.path.exists(f"seq/{accession}_1.fastq.gz"):
                        os.remove(f"seq/{accession}_1.fastq.gz")
                    if os.path.exists(f"seq/{accession}_2.fastq.gz"):
                        os.remove(f"seq/{accession}_2.fastq.gz")
                else:
                    if os.path.exists(f"seq/{accession}.fastq.gz"):
                        os.remove(f"seq/{accession}.fastq.gz")
                    
                print(f"Error: {e}, files deleted for sequencing {accession}. Retrying...")

        if not success:
            print(f"Failed to download sequencing {accession} after 5 attempts.")
        else:
            if library_type == "paired" and not (os.path.exists(f"seq/{accession}_1.fastq.gz") and os.path.exists(f"seq/{accession}_2.fastq.gz")):
                raise ValueError(f"Error: The sequencing data for {accession} could not be downloaded properly because it is paired-end sequencing, but only one fastq file was downloaded.")
            sra_files.append({"file_name" : command["file_name"], "platform" : command["platform"]})

    return sra_files

