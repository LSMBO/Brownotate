"""
Final merge step: Assembling gene models
==========================================
Client label: "Assembling gene models"

This step runs once, after all per-chunk workers have completed. It:
  1. Concatenates all per-chunk genes.raw.gb files into the final genes.raw.gb
  2. Optionally cleans up intermediate files (PSL, scipiogff) to free disk space

MongoDB tracking uses the top-level 'scipio' step status (not per-chunk).
"""

import os

from flask_app.step_status import mark_step_detail


def merge_genes_raw(run_id, genesraw_files_ordered, output_file, payload=None):
    """
    Concatenate all per-chunk genes.raw.gb files into a single output file.

    genesraw_files_ordered: list of file paths, already sorted by chunk index.
    Returns None on success, 'Error: ...' on failure.
    """
    mark_step_detail(run_id, 'scipio', 'Assembling gene models from all genome parts', payload=payload)
    try:
        with open(output_file, 'w') as out:
            for chunk_file in genesraw_files_ordered:
                with open(chunk_file, 'r') as inp:
                    out.write(inp.read())
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            return f'Error: genes.raw.gb is empty after merge'
        return None
    except Exception as exc:
        return f'Error: merge step raised an exception: {exc}'


def cleanup_intermediates(work_dir):
    """
    Remove large intermediate files for one chunk to free disk space.
    Set env var BROWNOTATE_KEEP_SCIPIO_INTERMEDIATES=1 to disable.
    """
    if os.environ.get('BROWNOTATE_KEEP_SCIPIO_INTERMEDIATES', '0') == '1':
        return
    for filename in ['prot.vs.genome.psl', 'scipio.scipiogff']:
        path = os.path.join(work_dir, filename)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
