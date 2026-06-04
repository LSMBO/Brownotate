"""
Step 2 of 2 per chunk: Parsing BLAT results
=============================================
Client label: "Parsing BLAT results (N/M)"

This step covers everything from an existing .psl to a genes.raw.gb file:
  1. run_scipio_parse  — Scipio.pl reads the .psl and writes the .yaml
  2. run_yaml2gff      — yaml2gff.pl converts the YAML to an intermediate GFF
  3. run_scipiogff2gff — scipiogff2gff.pl converts to the final GFF
  4. run_gff2gb        — gff2gbSmallDNA.pl produces genes.raw.gb

Each sub-step is tracked in MongoDB so Resume can restart exactly where it left off.
"""

import os
import subprocess
import shlex

from flask_app.process_manager import add_process, remove_process
from .chunk_db import mark_chunk, substep_completed
from .utils import read_last_chars, is_non_empty_file

_scipio_script_path = None
_conda_bin_path = None
_env = None


def init(scipio_script_path, conda_bin_path, env):
    global _scipio_script_path, _conda_bin_path, _env
    _scipio_script_path = scipio_script_path
    _conda_bin_path = conda_bin_path
    _env = env


# ── Sub-step 1: Scipio.pl PSL → YAML ────────────────────────────────────────

def run_scipio_parse(run_id, assembly_file, evidence_file, work_dir, flex=False, payload=None):
    """
    Run Scipio.pl against an existing PSL to produce the YAML annotation file.

    Because the PSL already exists, Scipio.pl skips the BLAT phase entirely.
    If the YAML already exists and is non-empty, the step is skipped.

    Returns None on success, 'Error: ...' on failure.
    """
    protgenomepsl = os.path.join(work_dir, 'prot.vs.genome.psl')
    scipioyaml = os.path.join(work_dir, 'scipio.yaml')
    stderr_path = os.path.join(work_dir, 'scipio.stderr.log')

    if is_non_empty_file(scipioyaml):
        mark_chunk(run_id, work_dir, 'scipio_parsing', 'completed',
                   'Existing YAML found; skipping re-parsing',
                   payload=payload, result=scipioyaml)
        print(f"({os.path.basename(work_dir)}) YAML already exists — skipping Scipio parse.")
        return None

    if not flex:
        command = (
            f'perl {_scipio_script_path}/scipio.1.4.1.pl'
            f' --blat_output={protgenomepsl}'
            f' {assembly_file} {evidence_file}'
        )
    else:
        command = (
            f'perl {_scipio_script_path}/scipio.1.4.1.pl'
            f' --blat_output={protgenomepsl}'
            f' --min_identity=50 --min_coverage=50 --min_score=0.2'
            f' {assembly_file} {evidence_file}'
        )

    print(f"\n({os.path.basename(work_dir)}) [Scipio parse] {command}")
    mark_chunk(run_id, work_dir, 'scipio_parsing', 'running',
               'Parsing BLAT alignments: building gene models from PSL file',
               payload=payload, result={'psl': protgenomepsl})

    process_id = None
    try:
        command_args = shlex.split(command)
        # Safety: only open for writing if YAML is still empty/absent
        if is_non_empty_file(scipioyaml):
            mark_chunk(run_id, work_dir, 'scipio_parsing', 'completed',
                       'YAML appeared just before write — skipping',
                       payload=payload, result=scipioyaml)
            return None

        with open(scipioyaml, 'w') as out, open(stderr_path, 'w') as err:
            process = subprocess.Popen(
                command_args, env=_env, text=True,
                stdout=out, stderr=err,
                preexec_fn=os.setsid
            )
            process_id = process.pid
            add_process(run_id, process_id, command, 1)
            returncode = process.wait()

        stderr_msg = read_last_chars(stderr_path)
        yaml_exists = is_non_empty_file(scipioyaml)

        if returncode != 0:
            if yaml_exists:
                # Scipio.pl exits non-zero for chunks with no alignable proteins,
                # but still writes a valid (possibly tiny) YAML — that's OK.
                mark_chunk(run_id, work_dir, 'scipio_parsing', 'completed',
                           'Scipio.pl exited non-zero but produced a valid YAML',
                           payload=payload, result=scipioyaml)
                print(f"({os.path.basename(work_dir)}) Non-zero exit but YAML exists; continuing.")
                return None
            mark_chunk(run_id, work_dir, 'scipio_parsing', 'error',
                       f'Scipio.pl failed: {stderr_msg[:500]}', payload=payload)
            return f'Error: Scipio.pl produced no YAML for {os.path.basename(assembly_file)}. Command: {command}'

        mark_chunk(run_id, work_dir, 'scipio_parsing', 'completed',
                   'YAML produced successfully',
                   payload=payload, result=scipioyaml)
        return None

    except Exception as exc:
        mark_chunk(run_id, work_dir, 'scipio_parsing', 'error', str(exc), payload=payload)
        return f'Error: Scipio parse step raised an exception: {exc}'
    finally:
        if process_id:
            remove_process(process_id)


# ── Sub-step 2: yaml2gff ─────────────────────────────────────────────────────

def run_yaml2gff(run_id, work_dir, chunk_state, payload=None):
    """Convert scipio.yaml → scipio.scipiogff (intermediate GFF)."""
    scipioyaml = os.path.join(work_dir, 'scipio.yaml')
    scipioscipiogff = os.path.join(work_dir, 'scipio.scipiogff')

    if substep_completed(chunk_state, 'yaml2gff', scipioscipiogff):
        mark_chunk(run_id, work_dir, 'yaml2gff', 'completed',
                   'Existing intermediate GFF found; skipping yaml2gff',
                   payload=payload, result=scipioscipiogff)
        return None

    command = f'perl {_scipio_script_path}/yaml2gff.1.4.pl'
    print(f"\n({os.path.basename(work_dir)}) [yaml2gff] {command}")
    mark_chunk(run_id, work_dir, 'yaml2gff', 'running',
               'Converting YAML gene models to intermediate GFF format', payload=payload)

    process_id = None
    try:
        command_args = shlex.split(command)
        with open(scipioyaml, 'rb') as fin, open(scipioscipiogff, 'wb') as fout:
            process = subprocess.Popen(
                command_args, stdin=fin, stdout=fout,
                stderr=subprocess.PIPE, preexec_fn=os.setsid
            )
            process_id = process.pid
            add_process(run_id, process_id, command, 1)
            _, stderr = process.communicate()

        stderr_msg = stderr.decode(errors='ignore') if stderr else ''
        if process.returncode != 0 or not is_non_empty_file(scipioscipiogff):
            mark_chunk(run_id, work_dir, 'yaml2gff', 'error',
                       f'yaml2gff failed: {stderr_msg[:500]}', payload=payload)
            return f'Error: yaml2gff failed. stderr: {stderr_msg}'

        mark_chunk(run_id, work_dir, 'yaml2gff', 'completed',
                   'Intermediate GFF produced', payload=payload, result=scipioscipiogff)
        return None

    except Exception as exc:
        mark_chunk(run_id, work_dir, 'yaml2gff', 'error', str(exc), payload=payload)
        return f'Error: yaml2gff raised an exception: {exc}'
    finally:
        if process_id:
            remove_process(process_id)


# ── Sub-step 3: scipiogff2gff ─────────────────────────────────────────────────

def run_scipiogff2gff(run_id, work_dir, chunk_state, payload=None):
    """Convert scipio.scipiogff → scipio.gff (final GFF)."""
    scipioscipiogff = os.path.join(work_dir, 'scipio.scipiogff')
    scipiogff = os.path.join(work_dir, 'scipio.gff')

    if substep_completed(chunk_state, 'scipiogff2gff', scipiogff):
        mark_chunk(run_id, work_dir, 'scipiogff2gff', 'completed',
                   'Existing final GFF found; skipping scipiogff2gff',
                   payload=payload, result=scipiogff)
        return None

    command = f'perl {_conda_bin_path}/scipiogff2gff.pl --in={scipioscipiogff} --out={scipiogff}'
    print(f"\n({os.path.basename(work_dir)}) [scipiogff2gff] {command}")
    mark_chunk(run_id, work_dir, 'scipiogff2gff', 'running',
               'Converting intermediate GFF to final GFF', payload=payload)

    process_id = None
    try:
        command_args = shlex.split(command)
        process = subprocess.Popen(
            command_args, env=_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        process_id = process.pid
        add_process(run_id, process_id, command, 1)
        _, stderr = process.communicate()

        stderr_msg = stderr.decode(errors='ignore') if stderr else ''
        if process.returncode != 0 or not is_non_empty_file(scipiogff):
            mark_chunk(run_id, work_dir, 'scipiogff2gff', 'error',
                       f'scipiogff2gff failed: {stderr_msg[:500]}', payload=payload)
            return f'Error: scipiogff2gff failed. Command: {command}. stderr: {stderr_msg}'

        mark_chunk(run_id, work_dir, 'scipiogff2gff', 'completed',
                   'Final GFF produced', payload=payload, result=scipiogff)
        return None

    except Exception as exc:
        mark_chunk(run_id, work_dir, 'scipiogff2gff', 'error', str(exc), payload=payload)
        return f'Error: scipiogff2gff raised an exception: {exc}'
    finally:
        if process_id:
            remove_process(process_id)


# ── Sub-step 4: gff2gbSmallDNA ───────────────────────────────────────────────

def run_gff2gb(run_id, assembly_file, work_dir, chunk_state, payload=None):
    """Convert scipio.gff + genome chunk → genes.raw.gb (GenBank format)."""
    scipiogff = os.path.join(work_dir, 'scipio.gff')
    genesrawgb = os.path.join(work_dir, 'genes.raw.gb')

    if substep_completed(chunk_state, 'gff2gb', genesrawgb):
        mark_chunk(run_id, work_dir, 'gff2gb', 'completed',
                   'Existing genes.raw.gb found; skipping gff2gb',
                   payload=payload, result=genesrawgb)
        return None

    command = f'perl {_conda_bin_path}/gff2gbSmallDNA.pl {scipiogff} {assembly_file} 1000 {genesrawgb}'
    print(f"\n({os.path.basename(work_dir)}) [gff2gb] {command}")
    mark_chunk(run_id, work_dir, 'gff2gb', 'running',
               'Building GenBank training file from gene annotations', payload=payload)

    process_id = None
    try:
        command_args = shlex.split(command)
        process = subprocess.Popen(
            command_args, env=_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        process_id = process.pid
        add_process(run_id, process_id, command, 1)
        _, stderr = process.communicate()

        stderr_msg = stderr.decode(errors='ignore') if stderr else ''
        if process.returncode != 0 or not is_non_empty_file(genesrawgb):
            mark_chunk(run_id, work_dir, 'gff2gb', 'error',
                       f'gff2gbSmallDNA failed: {stderr_msg[:500]}', payload=payload)
            return f'Error: gff2gbSmallDNA failed. Command: {command}. stderr: {stderr_msg}'

        _clean_genbank_file(genesrawgb)
        mark_chunk(run_id, work_dir, 'gff2gb', 'completed',
                   'genes.raw.gb produced successfully',
                   payload=payload, result=genesrawgb)
        return None

    except Exception as exc:
        mark_chunk(run_id, work_dir, 'gff2gb', 'error', str(exc), payload=payload)
        return f'Error: gff2gb raised an exception: {exc}'
    finally:
        if process_id:
            remove_process(process_id)


# ── GenBank cleanup ───────────────────────────────────────────────────────────

def _clean_genbank_file(gb_file):
    """Remove malformed entries (0 bp sequences, negative coordinates) from a GenBank file."""
    with open(gb_file, 'r') as fh:
        content = fh.read()
    entries = content.split('//\n')
    valid = [e for e in entries if e.strip() and '0 bp' not in e and '..-' not in e]
    with open(gb_file, 'w') as fh:
        fh.write('//\n'.join(valid) + ('//\n' if valid else ''))
