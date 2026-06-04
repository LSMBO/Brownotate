"""
Scipio annotation pipeline — Flask blueprint
=============================================

Progress labels shown to the client:
  "BLAT alignment (N/M)"        — per-chunk BLAT step
  "Parsing BLAT results (N/M)"  — per-chunk PSL→YAML→GFF→GB
  "Assembling gene models"      — final merge of all genes.raw.gb

Entry point: POST /run_scipio
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, request, jsonify
from flask_app.utils import load_config
from flask_app.step_status import mark_step_error, mark_step_running, mark_step_success, mark_step_detail
from flask_app.process_manager import remove_run_processes
from timer import timer

from .chunk_db import mark_chunk
from .utils import (
    order_chunks_by_size,
    resolve_worker_count,
    try_acquire_lock,
    release_lock,
    wait_for_result,
)
from .worker import run_chunk_safe
from .merge_step import merge_genes_raw
from . import blat_step, parse_step

# ── module-level init ────────────────────────────────────────────────────────

run_scipio_bp = Blueprint('run_scipio_bp', __name__)
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

_scipio_script_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + '/ext'
_conda_bin_path = f"{config['BROWNOTATE_ENV_PATH']}/bin"

# Inject shared config into sub-modules
blat_step.init(_scipio_script_path, env)
parse_step.init(_scipio_script_path, _conda_bin_path, env)


# ── helpers ──────────────────────────────────────────────────────────────────

def _progress_label(completed, total, workers, phase, resumed=False):
    """
    Build a human-readable progress string for the client.

    phase: 'blat' or 'parse'
    Examples:
      "BLAT alignment (1/2)"
      "Parsing BLAT results (2/2)"
    """
    total_steps = max(1, (total + workers - 1) // workers)
    current_step = min(total_steps, max(1, (completed // workers) + 1))

    if phase == 'blat':
        label = 'BLAT alignment'
    else:
        label = 'Parsing BLAT results'

    if resumed:
        label = f'Resuming: {label}'

    return f'{label} ({current_step}/{total_steps})'


# ── Flask route ───────────────────────────────────────────────────────────────

@run_scipio_bp.route('/run_scipio', methods=['POST'])
def run_scipio():
    """Main entry point for the chunked Scipio annotation workflow."""
    start_time = timer.start()
    parameters = request.json.get('parameters')
    flex = bool(request.json.get('flex'))
    evidence_file = request.json.get('evidence_file')
    run_id = parameters['id']
    cpus = parameters['cpus']
    split_assembly_files = request.json.get('split_assembly_files')
    step_payload = {'flex': flex}

    mark_step_running(run_id, 'scipio', payload=step_payload, detail='Preparing Scipio workspace')
    annotation_dir = f'runs/{run_id}/annotation'
    os.makedirs(annotation_dir, exist_ok=True)
    genesraw = f'{annotation_dir}/genes.raw.gb'
    lock_file = f'{annotation_dir}/.scipio.lock'

    # ── Validate inputs ───────────────────────────────────────────────────────
    if not evidence_file or str(evidence_file).strip().lower() == 'none' or not os.path.exists(str(evidence_file)):
        elapsed = timer.stop(start_time)
        msg = f'Invalid evidence file for Scipio: {evidence_file}'
        mark_step_error(run_id, 'scipio', msg, payload=step_payload)
        return jsonify({'status': 'error', 'message': msg, 'timer': elapsed}), 500

    # ── Already fully done? ───────────────────────────────────────────────────
    if os.path.exists(genesraw) and os.path.getsize(genesraw) > 0:
        elapsed = timer.stop(start_time)
        mark_step_success(run_id, 'scipio', result=genesraw, timer_value=elapsed, payload=step_payload)
        return jsonify({'status': 'success', 'data': genesraw, 'timer': elapsed}), 200

    # ── Acquire run lock ──────────────────────────────────────────────────────
    lock_fd = try_acquire_lock(lock_file)
    if lock_fd is None:
        if wait_for_result(genesraw, lock_file):
            elapsed = timer.stop(start_time)
            mark_step_success(run_id, 'scipio', result=genesraw, timer_value=elapsed, payload=step_payload)
            return jsonify({'status': 'success', 'data': genesraw, 'timer': elapsed}), 200
        elapsed = timer.stop(start_time)
        mark_step_error(run_id, 'scipio', 'Scipio appears to have failed after network interruption.', payload=step_payload)
        return jsonify({'status': 'error', 'message': 'Scipio appears to have failed after a network interruption.', 'timer': elapsed}), 500

    try:
        total_chunks = len(split_assembly_files or [])
        if total_chunks == 0:
            elapsed = timer.stop(start_time)
            msg = 'No split assembly files were provided to Scipio.'
            mark_step_error(run_id, 'scipio', msg, payload=step_payload)
            return jsonify({'status': 'error', 'message': msg, 'timer': elapsed}), 500

        ordered_chunks = order_chunks_by_size(split_assembly_files)
        max_workers = resolve_worker_count(cpus, evidence_file, ordered_chunks)

        # ── Classify chunks: already done vs pending ──────────────────────────
        genesraw_files = []
        pending_jobs = []
        completed_chunks = 0

        for i, assembly_file in enumerate(ordered_chunks):
            work_dir = f'runs/{run_id}/annotation/scipio_work_dir_{i + 1}'
            os.makedirs(work_dir, exist_ok=True)
            existing_gb = f'{work_dir}/genes.raw.gb'
            if os.path.exists(existing_gb) and os.path.getsize(existing_gb) > 0:
                genesraw_files.append((i, existing_gb))
                completed_chunks += 1
                mark_chunk(run_id, work_dir, 'gff2gb', 'completed',
                           'genes.raw.gb already exists for this genome part',
                           payload=step_payload, result=existing_gb)
                mark_chunk(run_id, work_dir, 'chunk', 'completed',
                           'This genome part is already finished', payload=step_payload)
            else:
                mark_chunk(run_id, work_dir, 'queue', 'pending',
                           'Waiting to start Scipio processing', payload=step_payload)
                pending_jobs.append((i, assembly_file, work_dir))

        resumed = completed_chunks > 0
        mark_step_detail(
            run_id, 'scipio',
            _progress_label(completed_chunks, total_chunks, max_workers, 'blat', resumed=resumed),
            payload=step_payload
        )
        print(f"[scipio] run_id={run_id} workers={max_workers} evidence={evidence_file} "
              f"done={completed_chunks} pending={len(pending_jobs)}")

        # ── Run pending chunks in parallel ────────────────────────────────────
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    run_chunk_safe, run_id, assembly_file, evidence_file, work_dir,
                    flex=flex, payload=step_payload
                ): i
                for i, assembly_file, work_dir in pending_jobs
            }

            for future in as_completed(futures):
                res = future.result()
                if isinstance(res, str) and res.startswith('Error:'):
                    remove_run_processes(run_id)
                    elapsed = timer.stop(start_time)
                    mark_step_error(run_id, 'scipio', res[7:], payload=step_payload)
                    return jsonify({'status': 'error', 'message': res[7:], 'timer': elapsed}), 500
                if not os.path.exists(res):
                    remove_run_processes(run_id)
                    elapsed = timer.stop(start_time)
                    msg = f'Expected output not found: {res}'
                    mark_step_error(run_id, 'scipio', msg, payload=step_payload)
                    return jsonify({'status': 'error', 'message': msg, 'timer': elapsed}), 500

                genesraw_files.append((futures[future], res))
                completed_chunks += 1
                if completed_chunks < total_chunks:
                    mark_step_detail(
                        run_id, 'scipio',
                        _progress_label(completed_chunks, total_chunks, max_workers, 'parse', resumed=resumed),
                        payload=step_payload
                    )

        # ── Merge all genes.raw.gb ────────────────────────────────────────────
        ordered_gb = [path for _, path in sorted(genesraw_files, key=lambda x: x[0])]
        error = merge_genes_raw(run_id, ordered_gb, genesraw, payload=step_payload)
        if error:
            remove_run_processes(run_id)
            elapsed = timer.stop(start_time)
            mark_step_error(run_id, 'scipio', error[7:], payload=step_payload)
            return jsonify({'status': 'error', 'message': error[7:], 'timer': elapsed}), 500

        remove_run_processes(run_id)
        elapsed = timer.stop(start_time)
        mark_step_success(run_id, 'scipio', result=genesraw, timer_value=elapsed,
                          payload=step_payload,
                          detail='Scipio annotation completed successfully')
        return jsonify({'status': 'success', 'data': genesraw, 'timer': elapsed}), 200

    finally:
        release_lock(lock_fd, lock_file)
