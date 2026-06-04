import os
import shutil

from flask import Blueprint, jsonify, request

from flask_app.commands import run_command
from flask_app.step_status import mark_step_detail, mark_step_error, mark_step_running, mark_step_success
from flask_app.utils import load_config
from timer import timer

from .training_utils import (
    collect_problematic_sequences,
    count_locus,
    count_stop_codon_messages,
    run_etraining,
)

run_model_bp = Blueprint('run_model_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
augustus_config_path = f"{config['BROWNOTATE_ENV_PATH']}/config"
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"
env['AUGUSTUS_CONFIG_PATH'] = augustus_config_path


@run_model_bp.route('/run_model', methods=['POST'])
def run_model():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    genesraw = request.json.get('genesraw')

    wd = parameters['id']
    mark_step_running(wd, 'model', detail='Preparing gene model training files')

    def fail(message, command=None, stdout=None, stderr=None, status_code=500):
        elapsed = timer.stop(start_time)
        mark_step_error(wd, 'model', message)
        payload = {
            'status': 'error',
            'message': message,
            'timer': elapsed,
        }
        if command is not None:
            payload['command'] = command
        if stderr is not None:
            payload['stderr'] = stderr
        if stdout is not None:
            payload['stdout'] = stdout
        return jsonify(payload), status_code

    if not genesraw or not os.path.exists(genesraw):
        return fail(f'genesraw input not found: {genesraw}', status_code=400)

    annotation_dir = f'runs/{wd}/annotation'
    os.makedirs(annotation_dir, exist_ok=True)

    # Remove zero-length genes before training.
    remove_zero_bp_genes(genesraw)

    mark_step_detail(wd, 'model', 'Initializing Augustus species model')
    command = f"perl {conda_bin_path}/new_species.pl --species={wd}"
    species_cfg_dir = f"{augustus_config_path}/species/{wd}"
    if os.path.exists(species_cfg_dir):
        shutil.rmtree(species_cfg_dir)

    stdout, stderr, returncode = run_command(command, wd, env=env)
    if returncode != 0:
        return fail('new_species.pl command failed', command=command, stdout=stdout, stderr=stderr)

    cfg_parameter_file = f"{species_cfg_dir}/{wd}_parameters.cfg"
    bonafide_stdout_path = f"{annotation_dir}/bonafide.out"
    bonafide_stderr_path = f"{annotation_dir}/bonafide.err"

    mark_step_detail(wd, 'model', 'Running etraining on genes.raw.gb')
    etrain_result = run_etraining(
        wd,
        wd,
        genesraw,
        bonafide_stdout_path,
        bonafide_stderr_path,
        env,
    )
    if etrain_result['returncode'] != 0:
        return fail(
            'etraining command failed',
            command=etrain_result['command'],
            stdout=etrain_result['stdout'],
            stderr=etrain_result['stderr'],
        )

    # If over half of genes miss stop codon, retrain with stopCodonExcludedFromCDS=true.
    num_genes_without_stop_codon = count_stop_codon_messages(bonafide_stderr_path)
    num_locus = count_locus(genesraw)

    if num_locus > 0 and num_genes_without_stop_codon > num_locus / 2:
        mark_step_detail(wd, 'model', 'Re-training etraining with stopCodonExcludedFromCDS=true')
        change_cfg_stop(cfg_parameter_file)

        etrain_result = run_etraining(
            wd,
            wd,
            genesraw,
            bonafide_stdout_path,
            bonafide_stderr_path,
            env,
            stop_codon_excluded=True,
        )
        if etrain_result['returncode'] != 0:
            return fail(
                'etraining command failed',
                command=etrain_result['command'],
                stdout=etrain_result['stdout'],
                stderr=etrain_result['stderr'],
            )

    badlst_path = f"{annotation_dir}/bad.lst"
    try:
        mark_step_detail(wd, 'model', 'Extracting problematic genes from etraining output')
        collect_problematic_sequences(bonafide_stderr_path, badlst_path)
    except Exception as exc:
        return fail('Error during problematic sequence processing', stderr=str(exc))

    genes_gb_path = f"{annotation_dir}/genes.gb"
    genes_gb_stderr = f"{annotation_dir}/genes.gb.err"

    mark_step_detail(wd, 'model', 'Filtering genes with filterGenes.pl')
    command = f"perl {conda_bin_path}/filterGenes.pl {badlst_path} {genesraw}"
    stdout, stderr, returncode = run_command(
        command,
        wd,
        stdout_path=genes_gb_path,
        stderr_path=genes_gb_stderr,
        env=env,
    )
    if returncode != 0:
        return fail('filterGenes command failed', command=command, stdout=stdout, stderr=stderr)

    num_genes_raw = count_locus(genesraw)
    num_genes = count_locus(genes_gb_path)
    print(f"Number of genes in genes.raw.gb: {num_genes_raw}")
    print(f"Number of genes in genes.gb: {num_genes}")

    elapsed = timer.stop(start_time)
    mark_step_success(
        wd,
        'model',
        result=num_genes,
        timer_value=elapsed,
        detail=f'Model training completed ({num_genes} genes retained)'
    )
    return jsonify({'status': 'success', 'data': num_genes, 'timer': elapsed}), 200


def change_cfg_stop(cfg_parameter_file):
    with open(cfg_parameter_file, 'r') as file:
        lines = file.readlines()

    with open(cfg_parameter_file, 'w') as file:
        for line in lines:
            if line.startswith('stopCodonExcludedFromCDS false'):
                line = line.replace('stopCodonExcludedFromCDS false', 'stopCodonExcludedFromCDS true')
            file.write(line)


def remove_zero_bp_genes(genesraw):
    cpt = 0
    with open(genesraw, 'r') as genesrawgb:
        lines = genesrawgb.readlines()

    with open(genesraw, 'w') as genesraw_file:
        for i, line in enumerate(lines):
            if line.endswith(' 0 bp  DNA\n') and i > 0 and lines[i - 1].startswith('LOCUS'):
                cpt += 1
                continue
            genesraw_file.write(line)

    return cpt
