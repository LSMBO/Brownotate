"""
Step 1 of 2 per chunk: BLAT alignment
======================================
Client label: "BLAT alignment (N/M)"

This step runs BLAT (via Scipio.pl's --blat_output flag) to align evidence
proteins against one genome chunk. It produces a .psl file.

The .psl is the expensive output — if it already exists and is non-empty, we
never redo this step, even if the DB says 'running' (which can happen when the
server is killed mid-run).

The BLAT executable itself is invoked by Scipio.pl internally. We only have
to call Scipio.pl with --only_blat to produce the PSL without the parsing phase.

NOTE: scipio.1.4.1.pl does not have a --only_blat flag. We therefore call it
normally when the PSL does not exist, which runs BLAT internaly and then parses.
If the PSL already exists, scipio.1.4.1.pl skips BLAT and goes straight to
parsing. We exploit this behaviour to separate the two stages logically:

  run_blat()     — called when prot.vs.genome.psl does not exist
  run_scipio_parse() — called when psl exists but scipio.yaml does not (in parse_step.py)

Both functions call the same Scipio.pl script, but resume logic decides which
one to invoke.
"""

import os
import subprocess
import shlex

from flask_app.process_manager import add_process, remove_process
from .chunk_db import mark_chunk
from .utils import read_last_chars, is_non_empty_file

# Resolved at import time from the app config (set by main.py after load_config)
_scipio_script_path = None
_env = None


def init(scipio_script_path, env):
    global _scipio_script_path, _env
    _scipio_script_path = scipio_script_path
    _env = env


def run_blat(run_id, assembly_file, evidence_file, work_dir, flex=False, payload=None):
    """
    Run BLAT via Scipio.pl to produce prot.vs.genome.psl.

    If the PSL already exists and is non-empty, the step is skipped immediately
    — we never redo an expensive BLAT when the output is already on disk.

    Returns None on success, an 'Error: ...' string on failure.
    """
    protgenomepsl = os.path.join(work_dir, 'prot.vs.genome.psl')

    # Hard safety: never redo BLAT if the PSL is already there
    if is_non_empty_file(protgenomepsl):
        mark_chunk(run_id, work_dir, 'blat_alignment', 'completed',
                   'Existing PSL found; skipping BLAT', payload=payload,
                   result={'psl': protgenomepsl})
        print(f"({os.path.basename(work_dir)}) PSL already exists — skipping BLAT.")
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

    # We redirect stdout to /dev/null here: we only want the PSL, not the YAML.
    # The YAML will be produced in parse_step.run_scipio_parse() which re-runs
    # Scipio.pl with the existing PSL.
    blat_stdout = os.path.join(work_dir, 'blat.stdout.log')
    stderr_path = os.path.join(work_dir, 'blat.stderr.log')

    print(f"\n({os.path.basename(work_dir)}) [BLAT alignment] {command}")
    mark_chunk(run_id, work_dir, 'blat_alignment', 'running',
               'Running BLAT: aligning evidence proteins against this genome part',
               payload=payload, result={'psl': protgenomepsl})

    process_id = None
    try:
        command_args = shlex.split(command)
        with open(blat_stdout, 'w') as out, open(stderr_path, 'w') as err:
            process = subprocess.Popen(
                command_args, env=_env, text=True,
                stdout=out, stderr=err,
                preexec_fn=os.setsid
            )
            process_id = process.pid
            add_process(run_id, process_id, command, 1)
            returncode = process.wait()

        stderr_msg = read_last_chars(stderr_path)

        if not is_non_empty_file(protgenomepsl):
            mark_chunk(run_id, work_dir, 'blat_alignment', 'error',
                       f'BLAT failed: no PSL produced. stderr: {stderr_msg[:500]}',
                       payload=payload)
            return f'Error: BLAT produced no PSL for {os.path.basename(assembly_file)}. stderr: {stderr_msg}'

        # PSL exists → BLAT succeeded (Scipio.pl may still exit non-zero for empty chunks)
        mark_chunk(run_id, work_dir, 'blat_alignment', 'completed',
                   'BLAT finished: PSL file produced',
                   payload=payload, result={'psl': protgenomepsl, 'returncode': returncode})
        print(f"({os.path.basename(work_dir)}) BLAT done → {protgenomepsl}")
        return None

    except Exception as exc:
        mark_chunk(run_id, work_dir, 'blat_alignment', 'error', str(exc), payload=payload)
        return f'Error: BLAT step raised an exception: {exc}'
    finally:
        if process_id:
            remove_process(process_id)
