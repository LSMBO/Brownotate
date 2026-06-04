"""
Shared utilities for the Scipio annotation pipeline.
"""

import os
import time
import psutil


def is_non_empty_file(path):
    """Return True if path exists and has size > 0."""
    return os.path.exists(path) and os.path.getsize(path) > 0


def remove_empty_file(path):
    """Delete a file only if it exists and is empty (0 bytes)."""
    try:
        if os.path.exists(path) and os.path.getsize(path) == 0:
            os.remove(path)
    except OSError:
        pass


def read_last_chars(file_path, max_chars=4000):
    """Return the last N characters of a file, for error reporting."""
    if not os.path.exists(file_path):
        return ''
    try:
        with open(file_path, 'r', errors='ignore') as handle:
            return handle.read()[-max_chars:].strip()
    except Exception:
        return ''


def order_chunks_by_size(assembly_files):
    """Sort genome chunks largest-first so big chunks start early."""
    def size(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    return sorted(assembly_files, key=size, reverse=True)


def estimate_worker_memory_gb(evidence_file, chunks):
    """Estimate peak RAM per Scipio worker based on input sizes."""
    evidence_gb = 0.0
    if evidence_file and os.path.exists(str(evidence_file)):
        evidence_gb = os.path.getsize(str(evidence_file)) / (1024 ** 3)

    if chunks:
        sizes = [os.path.getsize(c) for c in chunks if os.path.exists(c)]
        avg_chunk_gb = (sum(sizes) / len(sizes)) / (1024 ** 3) if sizes else 0.1
    else:
        avg_chunk_gb = 0.1

    # Tuned heuristic: lower fixed base, keep evidence/chunk impact significant.
    estimate = 8 + (avg_chunk_gb * 5) + (evidence_gb * 18)
    return max(8, min(32, estimate))


def resolve_worker_count(cpus, evidence_file, chunks):
    """
    Choose a safe parallel worker count based on CPU, RAM, and evidence size.
    Conservative: we never want to OOM the machine.
    """
    try:
        cpu_count = max(1, int(cpus))
    except (TypeError, ValueError):
        cpu_count = 1

    cpu_count = min(cpu_count, len(chunks) or 1)
    mem = psutil.virtual_memory()
    total_mem_gb = mem.total / (1024 ** 3)
    available_mem_gb = mem.available / (1024 ** 3)

    # Reserve 15% RAM for system + other services, bounded for stability.
    reserved_mem_gb = max(16, min(64, total_mem_gb * 0.15))
    worker_mem_gb = estimate_worker_memory_gb(evidence_file, chunks)
    mem_workers = max(1, int((available_mem_gb - reserved_mem_gb) // worker_mem_gb)) if available_mem_gb > reserved_mem_gb else 1

    evidence_mb = 0
    if evidence_file and os.path.exists(str(evidence_file)):
        evidence_mb = os.path.getsize(str(evidence_file)) / (1024 * 1024)

    if evidence_mb >= 300:
        io_cap = 6
    elif evidence_mb >= 150:
        io_cap = 8
    elif evidence_mb >= 60:
        io_cap = 10
    else:
        io_cap = 12

    # Larger-memory hosts can tolerate more concurrent BLAT workers.
    if total_mem_gb >= 220:
        io_cap += 4
    elif total_mem_gb >= 120:
        io_cap += 2

    io_cap = min(16, io_cap)

    return max(1, min(cpu_count, mem_workers, io_cap))


# ── lock helpers ────────────────────────────────────────────────────────────

def try_acquire_lock(lock_file):
    """Try to create a lock file. Returns an open fd on success, None if already locked."""
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as fh:
                content = fh.read().strip()
            if content.startswith('pid='):
                pid = int(content.split('=', 1)[1])
                try:
                    os.kill(pid, 0)  # check process alive
                except OSError:
                    os.remove(lock_file)  # stale lock
            else:
                os.remove(lock_file)
        except Exception:
            try:
                os.remove(lock_file)
            except OSError:
                pass

    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid={os.getpid()}\n".encode())
        return fd
    except FileExistsError:
        return None


def release_lock(fd, lock_file):
    """Release a lock file acquired with try_acquire_lock."""
    try:
        if fd is not None:
            os.close(fd)
    finally:
        try:
            os.remove(lock_file)
        except OSError:
            pass


def wait_for_result(output_file, lock_file, timeout=3600, poll=5):
    """
    Block until output_file appears or lock_file disappears.
    Used when a second request arrives while Scipio is already running.
    """
    waited = 0
    while waited < timeout:
        if is_non_empty_file(output_file):
            return True
        if not os.path.exists(lock_file):
            return is_non_empty_file(output_file)
        time.sleep(poll)
        waited += poll
    return is_non_empty_file(output_file)
