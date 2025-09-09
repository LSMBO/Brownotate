import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import json
import shlex
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.process_manager import add_process, remove_process
import shutil
import traceback

run_scipio_bp = Blueprint('run_scipio_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"
scipio_script_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/ext"

@run_scipio_bp.route('/run_scipio', methods=['POST'])
def run_scipio():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    flex = request.json.get('flex')
    evidence_file = request.json.get('evidence_file')
    run_id = parameters['id']
    cpus = parameters['cpus']
    split_assembly_files = request.json.get('split_assembly_files')

    # temp code to fake the process
    # shutil.copy('runs/fake_run/annotation/genes.raw.gb', f'runs/{run_id}/annotation/genes.raw.gb')
    # return jsonify({'status': 'success', 'data': f'runs/{run_id}/annotation/genes.raw.gb', 'timer': timer.stop(start_time)}), 200
    ##
    

    with ThreadPoolExecutor(max_workers=cpus) as executor:
        results = []
        for i, assembly_file in enumerate(split_assembly_files):
            work_dir = f"runs/{run_id}/annotation/scipio_work_dir_{i+1}"
            os.makedirs(work_dir, exist_ok=True)
            
            if not flex:
                result = executor.submit(run_scipio_worker, run_id, assembly_file, evidence_file, work_dir)
            else:
                result = executor.submit(run_flexible_scipio_worker, run_id, assembly_file, evidence_file, work_dir)
            results.append(result)
 
        genesraw_files = []
        for result in as_completed(results):
            res = result.result()
            if res.startswith('Error:'):
                remove_process(run_id)
                return jsonify({'status': 'error', 'message': res[7:], 'timer': timer.stop(start_time)}), 500
            if not os.path.exists(res):
                remove_process(run_id)
                return jsonify({'status': 'error', 'message': f'File not found: {res}', 'timer': timer.stop(start_time) }), 500
            genesraw_files.append(res)
        
        genesraw = f"runs/{run_id}/annotation/genes.raw.gb" 
        concatenate_files(genesraw_files, genesraw)
        # clean(split_assembly_files, run_id)
        remove_process(run_id)
        return jsonify({'status': 'success', 'data': genesraw, 'timer': timer.stop(start_time)}), 200
        
def run_scipio_worker(run_id, assembly_file, evidence_file, work_dir):
    max_blat_attempts = 3
    blat_attempt_count = 0
    protgenomepsl = f"{work_dir}/prot.vs.genome.psl"
    scipioyaml = f"{work_dir}/scipio.yaml"    
    while blat_attempt_count < max_blat_attempts and (not os.path.exists(f"{work_dir}/scipio.yaml") or os.path.getsize(f"{work_dir}/scipio.yaml") == 0):
        blat(run_id, assembly_file, evidence_file, protgenomepsl, scipioyaml) 
        blat_attempt_count += 1
    if not os.path.exists(f"{work_dir}/scipio.yaml") or os.path.getsize(f"{work_dir}/scipio.yaml") == 0:
        return f"Error: scipio.yaml not found after {max_blat_attempts} attempts of scipio.1.4.1.pl"
    if not os.path.exists(f"{work_dir}/scipio.gff"):
        extract_gff_from_yaml(run_id, scipioyaml, f"{work_dir}/scipio.scipiogff", f"{work_dir}/scipio.gff")  
    if not os.path.exists(f"{work_dir}/genes.raw.gb"):
        gff_to_genbank(run_id, assembly_file, f"{work_dir}/genes.raw.gb", f"{work_dir}/scipio.gff") 
    return f"{work_dir}/genes.raw.gb"

def run_flexible_scipio_worker(run_id, assembly_file, evidence_file, work_dir):
    max_blat_attempts = 3
    blat_attempt_count = 0
    protgenomepsl = f"{work_dir}/prot.vs.genome.psl"
    scipioyaml = f"{work_dir}/scipio.yaml"
    try:
        while blat_attempt_count < max_blat_attempts and (not os.path.exists(f"{work_dir}/scipio.yaml") or os.path.getsize(f"{work_dir}/scipio.yaml") == 0):
            blat(run_id, assembly_file, evidence_file, protgenomepsl, scipioyaml, flex=True) 
            blat_attempt_count += 1
        if not os.path.exists(f"{work_dir}/scipio.yaml"):
            return f"Error: scipio.yaml not found after {max_blat_attempts} attempts of scipio.1.4.1.pl"
        if not os.path.exists(f"{work_dir}/scipio.gff"):
            extract_gff_from_yaml(run_id, scipioyaml, f"{work_dir}/scipio.scipiogff", f"{work_dir}/scipio.gff")
        if not os.path.exists(f"{work_dir}/genes.raw.gb"):
            gff_to_genbank(run_id, assembly_file, f"{work_dir}/genes.raw.gb", f"{work_dir}/scipio.gff") 
        return f"{work_dir}/genes.raw.gb"
    except Exception as e:
        traceback.print_exc()
        return f"Error: Exception occurred in run_flexible_scipio_worker: {str(e)}"
        
def blat(run_id, assembly_file, evidence_file, protgenomepsl, scipioyaml, flex=False):
    if not flex:
        command = f'perl {scipio_script_path}/scipio.1.4.1.pl --blat_output={protgenomepsl} {assembly_file} {evidence_file} > {scipioyaml}'
    else:
        command = f'perl {scipio_script_path}/scipio.1.4.1.pl --blat_output={protgenomepsl} --min_identity=50 --min_coverage=50 --min_score=0.2 {assembly_file} {evidence_file} > {scipioyaml}'
    
    print(f"\n({os.path.basename(os.path.dirname(scipioyaml))})  {command}")
    process_id = None
    try:
        command_args = shlex.split(command)
        process = subprocess.Popen(command_args, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        process_id = process.pid
        add_process(run_id, process_id, command, 1)
        stdout, stderr = process.communicate()
    except subprocess.CalledProcessError as e:
        return f'Error: scipio failed for command {command}. stderr: {e.stderr.decode() if e.stderr else ""}'
    finally:
        if process_id:
            remove_process(run_id, process_id=process_id)
    
    
def extract_gff_from_yaml(run_id, scipioyaml, scipioscipiogff, scipiogff):
    if not os.path.exists(scipioscipiogff) or os.path.getsize(scipioscipiogff) == 0:
        command = f"cat {scipioyaml} | perl {scipio_script_path}/yaml2gff.1.4.pl > {scipioscipiogff}"
        
        print(f"\n({os.path.basename(os.path.dirname(scipioyaml))})  {command}")
        process_id = None
        try:
            command_args = shlex.split(command)
            process = subprocess.Popen(command_args, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
            process_id = process.pid
            add_process(run_id, process_id, command, 1)
            stdout, stderr = process.communicate()            
        except subprocess.CalledProcessError as e:
            return f'Error: scipio.scipiogff has not been generated. Command: {command}. stderr: {e.stderr.decode() if e.stderr else ""}'
        finally:
            if process_id:
                remove_process(run_id, process_id=process_id)
                
    command = f"perl {conda_bin_path}/scipiogff2gff.pl --in={scipioscipiogff} --out={scipiogff}"

    print(f"\n({os.path.basename(os.path.dirname(scipioyaml))})  {command}")
    process_id = None
    try:
        command_args = shlex.split(command)
        process = subprocess.Popen(command_args, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        process_id = process.pid
        add_process(run_id, process_id, command, 1)
        stdout, stderr = process.communicate()          
    except subprocess.CalledProcessError as e:
        return f"Error: scipiogff2gff failed for command {command}. stderr: {e.stderr.decode() if e.stderr else ''}"
    finally:
        if process_id:
            remove_process(run_id, process_id=process_id)    

def gff_to_genbank(run_id, assembly_file, genesrawgb, scipiogff):
    command = f"perl {conda_bin_path}/gff2gbSmallDNA.pl {scipiogff} {assembly_file} 1000 {genesrawgb}"
    print(f"\n({os.path.basename(os.path.dirname(genesrawgb))}) {command}")
    process_id = None
    try:
        command_args = shlex.split(command)
        process = subprocess.Popen(command_args, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        process_id = process.pid
        add_process(run_id, process_id, command, 1)
        stdout, stderr = process.communicate()        
    except subprocess.CalledProcessError as e:
        return f"Error: gff2gbSmallDNA failed for command {command}. stderr: {e.stderr.decode() if e.stderr else ''}"
    finally:
        if process_id:
            remove_process(run_id, process_id=process_id)        
    
def concatenate_files(input_files, output_file):
    with open(output_file, 'w') as outfile:
        for infile in input_files:
            with open(infile, 'r') as infile_handle:
                outfile.write(infile_handle.read())

def clean(split_assembly_files, run_id):
    for i in range(len(split_assembly_files)):
        work_dir = f"runs/{run_id}/annotation/scipio_work_dir_{i+1}"
        shutil.rmtree(work_dir)
    