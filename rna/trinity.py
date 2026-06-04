import os
import shutil
from flask import Blueprint, request, jsonify

from flask_app.commands import run_command
from timer import timer
from rna.common import env, ensure_rna_run_dir, existing_non_empty, get_rna_platform, prepare_rna_inputs, copy_artifact


run_trinity_bp = Blueprint('run_trinity_bp', __name__)


def _resolve_trinity_output(assembly_dir):
    direct_output = os.path.join(assembly_dir, 'Trinity.fasta')
    alternate_output = f"{assembly_dir}.Trinity.fasta"
    if existing_non_empty(direct_output):
        return direct_output
    if existing_non_empty(alternate_output):
        return alternate_output
    return None


@run_trinity_bp.route('/run_trinity', methods=['POST'])
def run_trinity():
    start_time = timer.start()
    try:
        payload = request.json or {}
        parameters = payload.get('parameters', {}) or {}
        run_id = int(payload.get('run_id') or parameters.get('id'))
        cpus = int(payload.get('cpus') or parameters.get('cpus') or 1)
        sequencing_file_list = payload.get('sequencing_file_list') or []

        platform = get_rna_platform(parameters)
        if platform in ('OXFORD_NANOPORE', 'PACBIO_SMRT'):
            return jsonify({
                'status': 'error',
                'message': 'Trinity does not support long-read RNA platforms. Use RNA-Bloom instead.',
                'timer': timer.stop(start_time)
            }), 400

        left_or_single, right, layout, input_error = prepare_rna_inputs(run_id, sequencing_file_list)
        if input_error:
            return jsonify({'status': 'error', 'message': input_error, 'timer': timer.stop(start_time)}), 400

        _, rna_dir, _ = ensure_rna_run_dir(run_id)
        assembly_dir = os.path.join(rna_dir, 'trinity')
        transcripts_file = os.path.join(rna_dir, 'trinity_transcripts.fasta')
        transcripts_alias = os.path.join(rna_dir, 'transcripts.fasta')

        if not existing_non_empty(transcripts_file):
            command = f"Trinity --seqType fq --CPU {cpus} --max_memory 250G --output {assembly_dir}"
            if layout == 'paired':
                command += f" --left {left_or_single} --right {right}"
            else:
                command += f" --single {left_or_single}"

            stdout, stderr, returncode = run_command(command, str(run_id), env=env)
            if returncode != 0:
                return jsonify({
                    'status': 'error',
                    'message': 'Trinity assembly failed',
                    'stderr': stderr,
                    'stdout': stdout,
                    'command': command,
                    'timer': timer.stop(start_time)
                }), 500

            trinity_output = _resolve_trinity_output(assembly_dir)
            if not trinity_output:
                return jsonify({'status': 'error', 'message': 'Trinity output file not found', 'timer': timer.stop(start_time)}), 500

            shutil.copy2(trinity_output, transcripts_file)

        copy_artifact(transcripts_file, transcripts_alias)

        return jsonify({
            'status': 'success',
            'data': {
                'transcripts_file': transcripts_file,
                'transcripts_alias_file': transcripts_alias,
                'assembly_dir': assembly_dir,
                'layout': layout,
                'assembler': 'trinity'
            },
            'timer': timer.stop(start_time)
        }), 200
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc), 'timer': timer.stop(start_time)}), 500