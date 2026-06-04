import os
import shutil
from flask import Blueprint, request, jsonify

from flask_app.commands import run_command
from timer import timer
from rna.common import env, ensure_rna_run_dir, existing_non_empty, fasta_record_count, copy_artifact


run_transdecoder_bp = Blueprint('run_transdecoder_bp', __name__)


def _species_brownotate_filename(parameters, run_id):
    scientific_name = str((parameters or {}).get('species', {}).get('scientificName') or '').strip()
    if not scientific_name:
        scientific_name = f"run_{run_id}"
    return f"{scientific_name.replace(' ', '_')}_Brownotate.fasta"


def _normalize_peptides_fasta(input_fasta, output_fasta):
    """Rewrite peptide FASTA with clean IDs and no trailing stop codon markers."""
    record_count = 0
    kept_count = 0

    with open(input_fasta, 'r') as reader, open(output_fasta, 'w') as writer:
        current_header = None
        sequence_chunks = []

        def flush_record(header, chunks):
            nonlocal record_count, kept_count
            if header is None:
                return

            record_count += 1
            sequence = ''.join(chunks).strip().replace(' ', '').replace('\t', '')
            sequence = sequence.rstrip('*')
            if not sequence:
                return

            kept_count += 1
            new_id = f"br_{kept_count:05d}"
            original_id = header[1:].split()[0] if header.startswith('>') else header.split()[0]
            writer.write(f">{new_id} source={original_id} method=transdecoder\n")
            for start in range(0, len(sequence), 80):
                writer.write(sequence[start:start + 80] + '\n')

        for raw_line in reader:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('>'):
                flush_record(current_header, sequence_chunks)
                current_header = line
                sequence_chunks = []
            else:
                sequence_chunks.append(line)

        flush_record(current_header, sequence_chunks)

    return record_count, kept_count


@run_transdecoder_bp.route('/run_transdecoder', methods=['POST'])
def run_transdecoder():
    start_time = timer.start()
    try:
        payload = request.json or {}
        parameters = payload.get('parameters', {}) or {}
        run_id = int(payload.get('run_id') or parameters.get('id'))
        transcripts_file = payload.get('transcripts_file')
        if not existing_non_empty(transcripts_file):
            return jsonify({'status': 'error', 'message': 'Transcriptome file is missing for TransDecoder', 'timer': timer.stop(start_time)}), 400

        _, rna_dir, _ = ensure_rna_run_dir(run_id)
        transdecoder_dir = os.path.abspath(os.path.join(rna_dir, 'transdecoder'))
        os.makedirs(transdecoder_dir, exist_ok=True)

        proteins_raw = os.path.join(rna_dir, 'transdecoder_raw.pep')
        proteins_clean = os.path.join(rna_dir, 'transdecoder_clean.pep')
        proteins_final = os.path.join(rna_dir, _species_brownotate_filename(parameters, run_id))
        normalized_tmp = os.path.join(rna_dir, 'transdecoder_clean.tmp.pep')

        if not existing_non_empty(proteins_raw):
            transcripts_abs = os.path.abspath(transcripts_file)
            transcripts_for_transdecoder = os.path.join(transdecoder_dir, os.path.basename(transcripts_abs))
            copy_artifact(transcripts_abs, transcripts_for_transdecoder)

            stdout, stderr, returncode = run_command(
                f"TransDecoder.LongOrfs -t {transcripts_for_transdecoder}",
                str(run_id),
                env=env,
                cwd=transdecoder_dir,
                stdout_path=os.path.join(transdecoder_dir, 'LongOrfs.log'),
                stderr_path=os.path.join(transdecoder_dir, 'LongOrfs.log')
            )
            if returncode != 0:
                return jsonify({
                    'status': 'error',
                    'message': 'TransDecoder.LongOrfs failed',
                    'stderr': stderr,
                    'stdout': stdout,
                    'timer': timer.stop(start_time)
                }), 500

            stdout, stderr, returncode = run_command(
                f"TransDecoder.Predict -t {transcripts_for_transdecoder}",
                str(run_id),
                env=env,
                cwd=transdecoder_dir,
                stdout_path=os.path.join(transdecoder_dir, 'Predict.log'),
                stderr_path=os.path.join(transdecoder_dir, 'Predict.log')
            )
            if returncode != 0:
                return jsonify({
                    'status': 'error',
                    'message': 'TransDecoder.Predict failed',
                    'stderr': stderr,
                    'stdout': stdout,
                    'timer': timer.stop(start_time)
                }), 500

            predicted_peptides = f"{transcripts_for_transdecoder}.transdecoder.pep"
            if not existing_non_empty(predicted_peptides):
                return jsonify({'status': 'error', 'message': 'TransDecoder output file not found', 'timer': timer.stop(start_time)}), 500

            copy_artifact(predicted_peptides, proteins_raw)

        source_for_normalization = proteins_raw

        _normalize_peptides_fasta(source_for_normalization, normalized_tmp)
        os.replace(normalized_tmp, proteins_clean)

        if fasta_record_count(proteins_clean) == 0:
            return jsonify({
                'status': 'error',
                'message': 'TransDecoder produced no usable proteins after peptide normalization',
                'detail': {
                    'transcripts_file': transcripts_file,
                    'transdecoder_raw_file': proteins_raw,
                    'transdecoder_clean_file': proteins_clean
                },
                'timer': timer.stop(start_time)
            }), 500

        copy_artifact(proteins_clean, proteins_final)

        # Keep only principal artifacts in rna/: final Brownotate FASTA and transcript files.
        for obsolete_file in (proteins_raw, proteins_clean, normalized_tmp):
            if os.path.exists(obsolete_file):
                try:
                    os.remove(obsolete_file)
                except OSError:
                    pass

        # Remove TransDecoder working folder after successful extraction.
        if os.path.isdir(transdecoder_dir):
            shutil.rmtree(transdecoder_dir, ignore_errors=True)

        return jsonify({
            'status': 'success',
            'data': {
                'proteins_raw_file': None,
                'proteins_clean_file': None,
                'proteins_for_brownaming_file': proteins_final,
                'proteins_legacy_file': None,
                'transdecoder_dir': transdecoder_dir
            },
            'timer': timer.stop(start_time)
        }), 200
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc), 'timer': timer.stop(start_time)}), 500
