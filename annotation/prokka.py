import os
import shutil
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify
from flask_app.commands import run_command
from Bio import SeqIO
from Bio.Seq import Seq

run_prokka_bp = Blueprint('run_prokka_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


@run_prokka_bp.route('/run_prokka', methods=['POST'])
def run_prokka():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    wd = parameters['id']
    cpus = parameters['cpus']
    assembly_file = request.json.get('assembly_file')
        
    if os.path.exists(f"runs/{wd}/annotation"):
        shutil.rmtree(f"runs/{wd}/annotation")
    
    scientific_name = parameters['species']['scientificName']
    annotation_file = f"runs/{wd}/annotation/{scientific_name.replace(' ', '_')}_Brownotate.fasta"
    
    command = f"prokka --outdir runs/{wd}/annotation --prefix prokka_annotation --cpus {cpus} --noanno --norrna --notrna {assembly_file}"
    stdout, stderr, returncode = run_command(command, wd, cpus=cpus)
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'Prokka command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
            'timer': timer.stop(start_time)
        }), 500    
    
    change_owner_recursive(f"runs/{wd}/annotation")
    clear_and_rename(wd, annotation_file)
    rename_fasta_headers(annotation_file)
    
    return jsonify({
        'status': 'success', 
        'data': annotation_file, 
        'timer': timer.stop(start_time)
    }), 200

def rename_fasta_headers(annotation_file):
    records = list(SeqIO.parse(annotation_file, "fasta"))
    new_records = []
    count = 0
    for record in records:
        count += 1
        new_id = f"br_{count:06d}"
        rec = SeqIO.SeqRecord(
            Seq(str(record.seq).upper()),
            id=new_id,
            description=""
        )
        new_records.append(rec)
    
    with open(annotation_file, "w") as f:
        SeqIO.write(new_records, f, "fasta")

def clear_and_rename(wd, annotation_file):
    files = os.listdir(f"runs/{wd}/annotation")
    for file in files:
        if file == "prokka_annotation.faa":
            os.rename(f"runs/{wd}/annotation/" + file, annotation_file)
        else:
            os.remove(f"runs/{wd}/annotation/" + file)

def change_owner_recursive(directory):
    user_uid = os.getuid()
    user_gid = os.getgid()

    for root, dirs, files in os.walk(directory):
        os.chown(root, user_uid, user_gid)
        for dir in dirs:
            os.chown(os.path.join(root, dir), user_uid, user_gid)
        for file in files:
            os.chown(os.path.join(root, file), user_uid, user_gid)
