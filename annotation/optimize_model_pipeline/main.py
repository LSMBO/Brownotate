import os

from flask import Blueprint, jsonify, request

from flask_app.commands import run_command
from flask_app.step_status import mark_step_detail, mark_step_error, mark_step_running, mark_step_success
from flask_app.utils import load_config
from timer import timer

from ..model_pipeline.training_utils import (
    extract_stop_probabilities,
    run_etraining,
    update_stop_probabilities,
)

run_optimize_model_bp = Blueprint('run_optimize_model_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
augustus_config_path = f"{config['BROWNOTATE_ENV_PATH']}/config"
conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"
env['AUGUSTUS_CONFIG_PATH'] = augustus_config_path


@run_optimize_model_bp.route('/run_optimize_model', methods=['POST'])
def run_optimize_model():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    num_genes = request.json.get('num_genes')

    wd = parameters['id']
    cpus = parameters['cpus']
    annotation_dir = f'runs/{wd}/annotation'
    genes_file = f'{annotation_dir}/genes.gb'

    mark_step_running(wd, 'optimize_model', detail='Preparing Augustus optimization inputs')

    def fail(message, command=None, stdout=None, stderr=None, status_code=500):
        elapsed = timer.stop(start_time)
        mark_step_error(wd, 'optimize_model', message)
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

    if not os.path.exists(genes_file):
        return fail(f'genes.gb file not found: {genes_file}', status_code=400)

    if num_genes > 300:
        mark_step_detail(wd, 'optimize_model', 'Splitting genes into train/test for optimization')
        command = f"perl {conda_bin_path}/randomSplit.pl {genes_file} 300"
        stdout, stderr, returncode = run_command(command, wd)
        if returncode != 0:
            return fail('randomSplit.pl command failed', command=command, stdout=stdout, stderr=stderr)

        train_genes_file = 'genes.gb.train'
        test_genes_file = 'genes.gb.test'
        command = (
            f"perl {conda_bin_path}/optimize_augustus.pl "
            f"--species={wd} --cpus={cpus} --kfold=8 --cleanup=1 "
            f"--onlytrain={train_genes_file} {test_genes_file}"
        )
    else:
        command = (
            f"perl {conda_bin_path}/optimize_augustus.pl "
            f"--species={wd} --cpus={cpus} --kfold=8 --cleanup=1 {os.path.basename(genes_file)}"
        )

    mark_step_detail(wd, 'optimize_model', 'Running optimize_augustus.pl')
    stdout, stderr, returncode = run_command(
        command,
        wd,
        cpus=cpus,
        stdout_path=f'{annotation_dir}/optimize.out',
        env=env,
        cwd=annotation_dir,
    )
    if returncode != 0:
        return fail('optimize_augustus.pl command failed', command=command, stdout=stdout, stderr=stderr)

    etrain_out = f'{annotation_dir}/etrain.out'
    etrain_err = f'{annotation_dir}/etrain.err'

    mark_step_detail(wd, 'optimize_model', 'Final etraining pass with optimized parameters')
    etrain_result = run_etraining(
        wd,
        wd,
        genes_file,
        etrain_out,
        etrain_err,
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

    mark_step_detail(wd, 'optimize_model', 'Applying stop codon probabilities to Augustus cfg')
    tag, taa, tga = extract_stop_probabilities(etrain_out)
    cfg_parameter_file = f'{augustus_config_path}/species/{wd}/{wd}_parameters.cfg'
    update_stop_probabilities(cfg_parameter_file, tag, taa, tga)

    elapsed = timer.stop(start_time)
    mark_step_success(
        wd,
        'optimize_model',
        result=True,
        timer_value=elapsed,
        detail='Model optimization completed successfully'
    )
    return jsonify({'status': 'success', 'timer': elapsed}), 200
