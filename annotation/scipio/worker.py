"""
Per-chunk orchestrator
=======================
Runs the full pipeline for one genome chunk:

  Stage 1 — "BLAT alignment"       (blat_step.run_blat)
  Stage 2 — "Parsing BLAT results" (parse_step: scipio_parse → yaml2gff → scipiogff2gff → gff2gb)

Resume logic:
  - If genes.raw.gb already exists → skip the whole chunk
  - If PSL exists                  → skip blat_alignment, go straight to parsing
  - Within parsing: each sub-step checks DB status + file existence
"""

import os
import traceback

from .chunk_db import mark_chunk, get_chunk_state, substep_completed
from .utils import is_non_empty_file, remove_empty_file
from . import blat_step, parse_step
from .merge_step import cleanup_intermediates


def run_chunk(run_id, assembly_file, evidence_file, work_dir,
              flex=False, payload=None):
    """
    Full pipeline for one genome chunk.
    Returns the path to genes.raw.gb on success, or 'Error: ...' on failure.
    """
    protgenomepsl = os.path.join(work_dir, 'prot.vs.genome.psl')
    scipioyaml    = os.path.join(work_dir, 'scipio.yaml')
    genesrawgb    = os.path.join(work_dir, 'genes.raw.gb')

    chunk_state = get_chunk_state(run_id, work_dir, payload)
    mark_chunk(run_id, work_dir, 'queue', 'running',
               'Processing started for this genome part', payload=payload)

    # ── Already done? ────────────────────────────────────────────────────────
    if substep_completed(chunk_state, 'gff2gb', genesrawgb):
        mark_chunk(run_id, work_dir, 'chunk', 'completed',
                   'Chunk already fully annotated', payload=payload, result=genesrawgb)
        return genesrawgb

    # ── Clean up any leftover empty files from a previous interrupted run ────
    # Only remove empty files; never touch non-empty outputs.
    for path in [scipioyaml,
                 os.path.join(work_dir, 'scipio.scipiogff'),
                 os.path.join(work_dir, 'scipio.gff'),
                 genesrawgb]:
        remove_empty_file(path)

    # ── Stage 1: BLAT alignment ──────────────────────────────────────────────
    # Skip if PSL already exists (non-empty) — we never redo BLAT.
    if not is_non_empty_file(protgenomepsl):
        error = blat_step.run_blat(
            run_id, assembly_file, evidence_file, work_dir,
            flex=flex, payload=payload
        )
        if error:
            mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
            return error
    else:
        mark_chunk(run_id, work_dir, 'blat_alignment', 'completed',
                   'Existing PSL found; skipping BLAT', payload=payload,
                   result={'psl': protgenomepsl})
        print(f"({os.path.basename(work_dir)}) PSL exists — skipping BLAT.")

    if not is_non_empty_file(protgenomepsl):
        error = f'Error: BLAT produced no PSL for {os.path.basename(assembly_file)}'
        mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
        return error

    # ── Stage 2a: Scipio.pl parse (PSL → YAML) ───────────────────────────────
    if not is_non_empty_file(scipioyaml):
        error = parse_step.run_scipio_parse(
            run_id, assembly_file, evidence_file, work_dir,
            flex=flex, payload=payload
        )
        if error:
            # Retry once in flexible mode if normal mode produced no YAML
            if not flex:
                print(f"({os.path.basename(work_dir)}) Retry in flexible mode.")
                error = parse_step.run_scipio_parse(
                    run_id, assembly_file, evidence_file, work_dir,
                    flex=True, payload=payload
                )
            if error:
                mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
                return error
    else:
        mark_chunk(run_id, work_dir, 'scipio_parsing', 'completed',
                   'Existing YAML found; skipping Scipio parse', payload=payload,
                   result=scipioyaml)
        print(f"({os.path.basename(work_dir)}) YAML exists — skipping Scipio parse.")

    if not is_non_empty_file(scipioyaml):
        psl_mb = round(os.path.getsize(protgenomepsl) / (1024 * 1024), 1) if os.path.exists(protgenomepsl) else 0
        error = (f'Error: Scipio produced alignments ({psl_mb} MB PSL) but no YAML '
                 f'for {os.path.basename(assembly_file)}')
        mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
        return error

    # Refresh chunk state before parsing sub-steps (YAML now exists)
    chunk_state = get_chunk_state(run_id, work_dir, payload)

    # ── Stage 2b: yaml2gff ───────────────────────────────────────────────────
    error = parse_step.run_yaml2gff(run_id, work_dir, chunk_state, payload=payload)
    if error:
        mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
        return error

    # ── Stage 2c: scipiogff2gff ──────────────────────────────────────────────
    chunk_state = get_chunk_state(run_id, work_dir, payload)
    error = parse_step.run_scipiogff2gff(run_id, work_dir, chunk_state, payload=payload)
    if error:
        mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
        return error

    # ── Stage 2d: gff2gb ─────────────────────────────────────────────────────
    chunk_state = get_chunk_state(run_id, work_dir, payload)
    error = parse_step.run_gff2gb(run_id, assembly_file, work_dir, chunk_state, payload=payload)
    if error:
        mark_chunk(run_id, work_dir, 'chunk', 'error', error[7:], payload=payload)
        return error

    # ── Done ─────────────────────────────────────────────────────────────────
    cleanup_intermediates(work_dir)
    mark_chunk(run_id, work_dir, 'chunk', 'completed',
               'Chunk annotation completed successfully',
               payload=payload, result=genesrawgb)
    return genesrawgb


def run_chunk_safe(run_id, assembly_file, evidence_file, work_dir,
                   flex=False, payload=None):
    """Wrapper that catches unexpected exceptions and returns an Error string."""
    try:
        return run_chunk(run_id, assembly_file, evidence_file, work_dir,
                         flex=flex, payload=payload)
    except Exception as exc:
        traceback.print_exc()
        mark_chunk(run_id, work_dir, 'chunk', 'error', str(exc), payload=payload)
        return f'Error: unexpected exception in chunk worker: {exc}'
