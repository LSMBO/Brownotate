"""
MongoDB helpers for per-chunk Scipio progress tracking.

Each genome chunk goes through two main stages:
  - blat_alignment : BLAT runs, produces a .psl file, then Scipio.pl parses it → .yaml
  - result_parsing : yaml2gff → scipiogff2gff → gff2gbSmallDNA → genes.raw.gb

Substep keys stored in MongoDB under resumeData.scipio_chunks.chunk_N:
  blat_alignment  — the BLAT step (produces prot.vs.genome.psl)
  scipio_parsing  — Scipio.pl parsing PSL → YAML
  yaml2gff        — yaml2gff.pl
  scipiogff2gff   — scipiogff2gff.pl
  gff2gb          — gff2gbSmallDNA.pl → genes.raw.gb
  chunk           — overall chunk status
"""

import os
from flask_app.database import find_one
from flask_app.step_status import mark_step_substatus


def chunk_key(work_dir):
    """Return a stable MongoDB-safe key for this chunk, e.g. 'chunk_7'."""
    suffix = os.path.basename(os.path.abspath(work_dir)).split('_')[-1]
    return f"chunk_{suffix}"


def mark_chunk(run_id, work_dir, substep, status, detail, payload=None, result=None):
    """Write one substep state to MongoDB for this chunk."""
    mark_step_substatus(
        run_id,
        'scipio',
        chunk_key(work_dir),
        substep,
        status,
        detail=detail,
        payload=payload,
        result=result,
    )


def get_chunk_state(run_id, work_dir, payload=None):
    """Read the last persisted state dict for this chunk from MongoDB."""
    step_key = 'scipio_flex' if (payload or {}).get('flex') else 'scipio'
    item_key = chunk_key(work_dir)
    for query in [
        {'parameters.id': run_id},
        {'parameters.id': int(run_id)} if isinstance(run_id, (int, str)) else None,
        {'parameters.id': str(run_id)},
    ]:
        if not query:
            continue
        result = find_one('runs', query)
        if result.get('status') == 'success' and result.get('data'):
            resume_data = result['data'].get('resumeData', {})
            return (resume_data.get(f'{step_key}_chunks') or {}).get(item_key, {})
    return {}


def substep_completed(chunk_state, substep, output_path=None):
    """Return True if this substep was completed according to DB (and output exists)."""
    if output_path and not (os.path.exists(output_path) and os.path.getsize(output_path) > 0):
        return False
    return chunk_state.get(substep, {}).get('status') == 'completed'
