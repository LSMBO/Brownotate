import subprocess
import os
from utils import load_config
from flask_app.process_manager import add_process, remove_process, get_process

config = load_config()

env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

def build_check_species_exists_command(species):
    return ["python", f"{config['BROWNOTATE_PATH']}/check_species_exists.py", "-s", species]
        
def build_dbsearch_command(species, current_datetime):
    arguments = ['-s', species, '--dbs-only', '-od', f'output_runs/{current_datetime}']
    return ["python", f"{config['BROWNOTATE_PATH']}/main.py"] + arguments

def build_brownotate_resume_command(run_id):
    arguments = ['--resume', run_id]
    return ["python", f"{config['BROWNOTATE_PATH']}/main.py"] + arguments
  
def build_brownotate_command(parameters, current_datetime):
    species = parameters['species']['taxonID']
    arguments = ['-s', species, '--run-id', current_datetime, '-od', f'output_runs/{current_datetime}']
    arguments += build_start_section_arguments(parameters['startSection'])
    arguments += build_annotation_section_arguments(parameters['annotationSection'])
    arguments += build_brownaming_section_arguments(parameters['brownamingSection'])
    arguments += build_busco_section_arguments(parameters['buscoSection'], parameters['startSection'])
    
    command = ["python", f"{config['BROWNOTATE_PATH']}/main.py"] + arguments
    return command

def build_start_section_arguments(start_section):
    arguments = []
    if start_section['sequencingFiles']:
        arguments += add_files_or_accessions(start_section['sequencingFilesList'], '-dfile')
    elif start_section['sequencingAccessions']:
        arguments += add_files_or_accessions(start_section['sequencingAccessionsList'], '-d')
    elif start_section['genomeFile']:
        if start_section['genomeFileIsURL']:
            arguments.append('-gu')
        else:
            arguments.append('-g')
        arguments.append(start_section['genomeFileList'][0])
        
    if start_section['skipFastp']:
        arguments.append('--skip-fastp')
            
    if start_section['skipPhix']:
        arguments.append('--skip-bowtie2')
    
    return arguments

def build_annotation_section_arguments(annotation_section):
    arguments = []
    if annotation_section['evidenceFile']:
        arguments += add_files_or_accessions(annotation_section['evidenceFileList'], '-e')
        
    # Nothing quoted : --skip-remove-redundancy
    # Same length (removeStrict) : default
    # Lower length (removeSoft) : --remove-included-sequence
    if annotation_section['removeSoft']:
        arguments.append('--remove-included-sequence')
    elif annotation_section['removeStrict'] == False:
        arguments.append('--skip-remove-redundancy')
    
    return arguments

def build_brownaming_section_arguments(brownaming_section):
    arguments = []
    if brownaming_section['skip']:
        arguments.append('--skip-brownaming')
    if brownaming_section['excludedSpeciesList']:
        for taxa in brownaming_section['excludedSpeciesList']:
            arguments += add_files_or_accessions(taxa, '--brownaming-exclude')
    if brownaming_section['highestRank']:
        arguments.append('--brownaming-maxrank')
        arguments.append(brownaming_section['highestRank'])
    
    return arguments

def build_busco_section_arguments(busco_section, start_section):
    arguments = []
    if not busco_section['assembly'] and not start_section['genomeFile']:
        arguments.append('--skip-busco-assembly')
    if not busco_section['annotation']:
        arguments.append('--skip-busco-annotation')
    
    return arguments

def add_files_or_accessions(items, flag):
    arguments = []
    for item in items:
        arguments.append(flag)
        arguments.append(item)
    return arguments

def run_command(command, run_id):
    process = None
    try:
        command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
        print(f"Running command from {os.getcwd()} with run_id={run_id}:\n{command}")
        process = subprocess.Popen(command, shell=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        add_process(run_id, process, command)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Command failed with returncode {process.returncode}")
            print(f"Error output: {stderr}")
        return stdout, stderr
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")
        print(f"Return code: {e.returncode}")
        print(f"Error output: {e.stderr}")
        return e.stdout, e.stderr
    finally:
        remove_process(run_id)
