"""
Batch generation for sequencing runs.

Generates combinations of sequencing runs that together provide adequate
genome coverage for assembly.
"""

from itertools import combinations


# Define platform categories
SHORT_READ_PLATFORMS = ['ILLUMINA', 'BGISEQ', 'ION_TORRENT']
LONG_READ_PLATFORMS = ['PACBIO_SMRT', 'OXFORD_NANOPORE']


def get_read_type(platform):
    """
    Determine if a platform is short-read or long-read.
    
    Args:
        platform: Platform name
        
    Returns:
        'short' or 'long'
    """
    if platform in SHORT_READ_PLATFORMS:
        return 'short'
    elif platform in LONG_READ_PLATFORMS:
        return 'long'
    else:
        return 'unknown'


def create_batch(runs, genome_size):
    """
    Create a batch dictionary from a list of runs.
    
    Args:
        runs: List of run dictionaries
        genome_size: Dictionary with genome size statistics
        
    Returns:
        Batch dictionary with metadata and statistics
    """
    total_bases = sum(run['total_bases'] for run in runs)
    coverage = total_bases / genome_size['mean'] if genome_size['mean'] > 0 else 0
    
    # Extract common metadata from first run
    first_run = runs[0]
    
    # Determine read type for this batch
    read_type = get_read_type(first_run.get('platform', ''))
    
    batch = {
        'runs': runs,
        'run_count': len(runs),
        'total_bases': total_bases,
        'coverage': coverage,
        'taxid': str(first_run['taxid']),
        'scientific_name': first_run['scientific_name'],
        'assembly_expected_size': genome_size['mean'],
        'assembly_expected_size_stats': genome_size,
        'read_type': read_type
    }
    
    return batch


def generate_batches_from_runs_simple(runs, size_limits, genome_size):
    """
    Simple batch generation with max 8 runs per batch.
    
    Strategy:
    1. Try single runs in the target range
    2. If none, try combinations of 2, 3, ... up to 8 runs
    3. For PacBio: prioritize HiFi runs
        
    Args:
        runs: List of run dictionaries (already deduplicated)
        size_limits: Tuple (min_size, max_size) in base pairs
        genome_size: Dictionary with genome size statistics
        
    Returns:
        List of batch dictionaries
    """
    min_size, max_size = size_limits
    max_batch_size = 8
    
    # Filter and sort runs
    # Priority: 1) HiFi first (for PacBio), 2) largest first
    valid_runs = [run for run in runs if run['total_bases'] <= max_size]
    valid_runs = sorted(
        valid_runs, 
        key=lambda r: (not r.get('is_hifi', False), -r['total_bases'])
    )[:25]
    
    if not valid_runs:
        return []
    
    batches = []
    used_accessions = set()
    
    # STEP 1: Single-run batches
    for run in valid_runs:
        if run['accession'] in used_accessions:
            continue
        if min_size <= run['total_bases'] <= max_size:
            batch = create_batch([run], genome_size)
            batches.append(batch)
            used_accessions.add(run['accession'])
    
    if batches:
        return batches
    
    # STEP 2: Try combinations
    for batch_size in range(2, min(max_batch_size + 1, len(valid_runs) + 1)):
        for combination in combinations(range(len(valid_runs)), batch_size):
            runs_subset = [valid_runs[idx] for idx in combination]
            
            # Skip if any run already used
            if any(run['accession'] in used_accessions for run in runs_subset):
                continue
            
            total_bases = sum(run['total_bases'] for run in runs_subset)
            
            if min_size <= total_bases <= max_size:
                batch = create_batch(runs_subset, genome_size)
                batches.append(batch)
                # Mark as used
                for run in runs_subset:
                    used_accessions.add(run['accession'])
                
                if len(batches) >= 20:
                    return batches
        
        if batches:
            break
    
    return batches
