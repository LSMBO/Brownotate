import os

from flask import Blueprint, request, jsonify

from flask_app.commands import run_command
from timer import timer
from rna.common import env, ensure_rna_run_dir, existing_non_empty, prepare_rna_inputs, copy_artifact


run_rnabloom_bp = Blueprint('run_rnabloom_bp', __name__)


def _find_rnabloom_output(assembly_dir):
    candidates = [
        'rnabloom.transcripts.nr.fa',
        'rnabloom.transcripts.fa',
        'rnabloom.transcripts.short.fa',
    ]
    for filename in candidates:
        candidate_path = os.path.join(assembly_dir, filename)
        if existing_non_empty(candidate_path):
            return candidate_path
    return None


@run_rnabloom_bp.route('/run_rnabloom', methods=['POST'])
def run_rnabloom():
    start_time = timer.start()
    try:
        payload = request.json or {}
        parameters = payload.get('parameters', {}) or {}
        run_id = int(payload.get('run_id') or parameters.get('id'))
        cpus = int(payload.get('cpus') or parameters.get('cpus') or 1)
        sequencing_file_list = payload.get('sequencing_file_list') or []

        left_or_single, right, layout, input_error = prepare_rna_inputs(run_id, sequencing_file_list)
        if input_error:
            return jsonify({'status': 'error', 'message': input_error, 'timer': timer.stop(start_time)}), 400

        _, rna_dir, _ = ensure_rna_run_dir(run_id)
        assembly_dir = os.path.join(rna_dir, 'rnabloom')
        transcripts_file = os.path.join(rna_dir, 'rnabloom_transcripts.fasta')
        transcripts_alias = os.path.join(rna_dir, 'transcripts.fasta')

        if not existing_non_empty(transcripts_file):
            command = f"rnabloom -t {cpus} -outdir {assembly_dir}"
            if layout == 'paired':
                command += f" -left {left_or_single} -right {right} -revcomp-right"
            else:
                command += f" -long {left_or_single}"

            stdout, stderr, returncode = run_command(command, str(run_id), env=env)
            if returncode != 0:
                return jsonify({
                    'status': 'error',
                    'message': 'RNA-Bloom assembly failed',
                    'stderr': stderr,
                    'stdout': stdout,
                    'command': command,
                    'timer': timer.stop(start_time)
                }), 500

            rnabloom_output = _find_rnabloom_output(assembly_dir)
            if not existing_non_empty(rnabloom_output):
                existing_outputs = sorted(os.listdir(assembly_dir)) if os.path.isdir(assembly_dir) else []
                return jsonify({
                    'status': 'error',
                    'message': 'RNA-Bloom output file not found',
                    'detail': {
                        'expected_outputs': [
                            'rnabloom.transcripts.nr.fa',
                            'rnabloom.transcripts.fa',
                            'rnabloom.transcripts.short.fa'
                        ],
                        'assembly_dir': assembly_dir,
                        'existing_outputs': existing_outputs[-20:]
                    },
                    'timer': timer.stop(start_time)
                }), 500

            os.replace(rnabloom_output, transcripts_file)

        copy_artifact(transcripts_file, transcripts_alias)

        return jsonify({
            'status': 'success',
            'data': {
                'transcripts_file': transcripts_file,
                'transcripts_alias_file': transcripts_alias,
                'assembly_dir': assembly_dir,
                'layout': layout,
                'assembler': 'rnabloom'
            },
            'timer': timer.stop(start_time)
        }), 200
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc), 'timer': timer.stop(start_time)}), 500
