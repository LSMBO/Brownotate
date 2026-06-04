import os
import shutil

from flask_app.utils import load_config


config = load_config()
env = os.environ.copy()
rna_env_path = config.get('BRNA_ENV_PATH') or config.get('BROWNOTATE_ENV_PATH')
if rna_env_path:
    env['PATH'] = os.path.join(rna_env_path, 'bin') + os.pathsep + env.get('PATH', '')


def strip_quotes(path_value):
    if not isinstance(path_value, str):
        return path_value
    value = path_value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def existing_non_empty(path_value):
    return isinstance(path_value, str) and os.path.exists(path_value) and os.path.getsize(path_value) > 0


def fasta_record_count(path_value):
    if not existing_non_empty(path_value):
        return 0

    count = 0
    with open(path_value, 'r') as handle:
        for line in handle:
            if line.startswith('>'):
                count += 1
    return count


def copy_artifact(source_path, destination_path):
    if not existing_non_empty(source_path):
        return None

    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    shutil.copy2(source_path, destination_path)
    return destination_path


def ensure_rna_run_dir(run_id):
    run_dir = os.path.join('runs', str(run_id))
    rna_dir = os.path.join(run_dir, 'rna')
    seq_dir = os.path.join(run_dir, 'seq')
    os.makedirs(rna_dir, exist_ok=True)
    os.makedirs(seq_dir, exist_ok=True)
    return run_dir, rna_dir, seq_dir


def collect_fastq_files(sequencing_file_list):
    paired = []
    single = []

    for entry in sequencing_file_list or []:
        files = entry.get('file_name') if isinstance(entry, dict) else entry
        if isinstance(files, list):
            clean_files = [strip_quotes(file_path) for file_path in files if existing_non_empty(strip_quotes(file_path))]
            if len(clean_files) >= 2:
                paired.append((clean_files[0], clean_files[1]))
            elif len(clean_files) == 1:
                single.append(clean_files[0])
        else:
            clean_file = strip_quotes(files)
            if existing_non_empty(clean_file):
                single.append(clean_file)

    return paired, single


def merge_fastq(inputs, output_path):
    with open(output_path, 'wb') as out_handle:
        for fastq_path in inputs:
            with open(fastq_path, 'rb') as in_handle:
                shutil.copyfileobj(in_handle, out_handle)


def prepare_rna_inputs(run_id, sequencing_file_list):
    _, _, seq_dir = ensure_rna_run_dir(run_id)
    paired, single = collect_fastq_files(sequencing_file_list)

    if paired and single:
        return None, None, None, 'Mixed paired-end and single-end RNA files are not supported in one run.'

    if paired:
        if len(paired) == 1:
            return paired[0][0], paired[0][1], 'paired', None

        merged_r1 = os.path.join(seq_dir, 'merged_rnaseq_R1.fastq')
        merged_r2 = os.path.join(seq_dir, 'merged_rnaseq_R2.fastq')
        merge_fastq([pair[0] for pair in paired], merged_r1)
        merge_fastq([pair[1] for pair in paired], merged_r2)
        return merged_r1, merged_r2, 'paired', None

    if single:
        if len(single) == 1:
            return single[0], None, 'single', None

        merged_single = os.path.join(seq_dir, 'merged_rnaseq_single.fastq')
        merge_fastq(single, merged_single)
        return merged_single, None, 'single', None

    return None, None, None, 'No valid RNA FASTQ files available for assembly.'


def get_rna_platform(parameters):
    return str(parameters.get('startSection', {}).get('rnaSequencingPlatform') or '').upper()
