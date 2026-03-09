import datetime
from flask import Blueprint, request, jsonify

from flask_app.database import insert_one
from timer import timer
from .genome_estimation import estimate_genome_size
from .sra_search import search_runs_for_species_simple, group_runs_by_taxid, get_run_by_accession
from .batch_generation import generate_batches_from_runs_simple


def search_dna_sequencing_batches(taxonomy, platforms, layout, coverage_lower, coverage_upper,
                                   strategy, selection, input_taxonomy_only=False, max_batch_count=5):
    """
    Search for DNA sequencing batches using client-provided parameters.
    
    Strategy:
    - Level-by-level search with early stop
    - For each taxonomic level (input species → parent → grandparent...):
      1. Search runs for that level (name + synonyms)
      2. Group by taxid (handles subspecies)
      3. Generate batches
      4. If batches found → STOP and return
    - Maximum 8 runs per batch
    - No automatic parameter relaxation (platforms/layout/strategy/selection always from user)
    - Lineage walk-up is NOT considered relaxation, just broader taxonomic search
    
    Args:
        taxonomy: Taxonomy dictionary with scientificName, taxonId, lineage, synonyms
        platforms: List of platform names (e.g., ['ILLUMINA', 'BGISEQ'])
        layout: Layout type ('PAIRED' or 'SINGLE' or None for long reads)
        coverage_lower: Minimum coverage (e.g., 50)
        coverage_upper: Maximum coverage (e.g., 80)
        strategy: Library strategy (e.g., 'WGS', or None)
        selection: Library selection (e.g., 'RANDOM', or None)
        input_taxonomy_only: If True, only search input species (no lineage walk)
        max_batch_count: Maximum number of batches to return
        
    Returns:
        List of batch dictionaries (sorted by coverage descending)
    """
    # Estimate genome size with coverage parameters
    genome_size = estimate_genome_size(taxonomy, coverage_lower, coverage_upper)
    
    # Calculate size limits based on user-provided coverage
    genome_mean = genome_size['mean']
    size_limits = (genome_mean * coverage_lower, genome_mean * coverage_upper)

    # Build search configuration (user parameters, no relaxation)
    search_config = {
        'platforms': platforms,
        'layout': layout,
        'strategy': strategy,
        'selection': selection
    }
    
    # Global blacklist to prevent duplicate runs from being returned by SRA searches  
    runs_blacklist = set()
    
    # Build taxonomic levels to search (level-by-level with early stop)
    taxonomic_levels = []
    
    # Level 1: Input species + synonyms
    input_names = [taxonomy['scientificName']] + taxonomy.get('synonyms', [])
    taxonomic_levels.append({
        'taxid': str(taxonomy['taxonId']),
        'names': input_names,
        'rank': 'input'
    })
    
    # Level 2+: Lineage (parent, grandparent, etc.)
    if not input_taxonomy_only:
        for taxo in taxonomy.get('lineage', []):
            names = [taxo['scientificName']] + taxo.get('synonyms', [])
            taxonomic_levels.append({
                'taxid': str(taxo['taxonId']),
                'names': names,
                'rank': taxo.get('rank', 'unknown')
            })
    
    # Try each taxonomic level until we find valid batches
    for level_idx, level in enumerate(taxonomic_levels):
        print(f"Searching level {level_idx + 1}/{len(taxonomic_levels)}: {level['names'][0]} ({level['rank']})")
        
        # Search runs for all names in this level
        level_runs = []
        for species_name in level['names']:
            runs = search_runs_for_species_simple(species_name, search_config, size_limits, runs_blacklist)
            level_runs.extend(runs)
        
        if not level_runs:
            print(f"  No runs found for {level['names'][0]}")
            continue
        
        print(f"  Found {len(level_runs)} unique runs for {level['names'][0]}")
        
        # Group by taxid (handles subspecies within this level)
        species_dict = group_runs_by_taxid(level_runs)
        
        # Generate batches for each taxid
        all_batches = []
        for taxid, runs in species_dict.items():
            batches = generate_batches_from_runs_simple(runs, size_limits, genome_size)
            all_batches.extend(batches)
        
        # If we found valid batches, stop here (early stop)
        if all_batches:
            print(f"  Generated {len(all_batches)} batches, stopping search")
            # Sort by coverage (descending) and limit
            sorted_batches = sorted(all_batches, key=lambda x: -x['coverage'])
            return sorted_batches[:max_batch_count]
        
        print(f"  No valid batches in coverage range, continuing to next level")
    
    # No batches found at any level
    print("No valid batches found at any taxonomic level")
    return []


dbs_dnaseq_bp = Blueprint('dbs_dnaseq_bp', __name__)

@dbs_dnaseq_bp.route('/dbs_dnaseq', methods=['POST'])
def dbs_dnaseq():
    """
    Main route for DNA sequencing data search.
    
    Searches for optimal batches of sequencing runs based on taxonomy and options.
    Stores results in MongoDB and returns them to client.
    
    Request JSON:
        user: User identifier
        taxonomy: Taxonomy dictionary with scientificName, taxonId, lineage, synonyms
        options: Dictionary with sequencing search parameters
        
    Returns:
        JSON with sequencing batches data
    """
    try:
        start_time = timer.start()
        
        # Extract request parameters
        user = request.json.get('user')
        taxonomy = request.json.get('taxonomy')
        options = request.json.get('options', {})
        current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")

        # Extract search options with defaults
        platforms = options.get('platforms', ['ILLUMINA'])
        if not isinstance(platforms, list):
            platforms = [platforms]  # Ensure it's always a list
        
        layout = options.get('layout', None)  # None means "any"
        if layout == 'any' or layout == '':
            layout = None
        
        coverage_lower = options.get('coverageLower', 50)
        coverage_upper = options.get('coverageUpper', 80)
        
        strategy = options.get('strategy', 'WGS')
        if strategy == 'any' or strategy == '':
            strategy = None
        
        selection = options.get('selection', 'RANDOM')
        if selection == 'any' or selection == '':
            selection = None
        
        input_taxonomy_only = options.get('inputTaxonomyOnly', False)
        max_batch_count = 5  # Fixed value, not from client
        
        if not user or not taxonomy:
            return jsonify({'error': 'Missing user or taxonomy'}), 400

        # Search for DNA sequencing batches
        dnaseq_batches = search_dna_sequencing_batches(
            taxonomy=taxonomy,
            platforms=platforms,
            layout=layout,
            coverage_lower=coverage_lower,
            coverage_upper=coverage_upper,
            strategy=strategy,
            selection=selection,
            input_taxonomy_only=input_taxonomy_only,
            max_batch_count=max_batch_count
        )

        timer_str = timer.stop(start_time)

        # Prepare database document
        mongo_query = {
            'user': user,
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': dnaseq_batches
        }
        
        # Insert into MongoDB
        insert_one('dnaseq', mongo_query)
        
        # Prepare clean response (without MongoDB ObjectId)
        response_data = {
            'user': user,
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': dnaseq_batches
        }
        
        return jsonify({'status': 'success', 'data': response_data}), 200
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error in dbs_dnaseq: {str(e)}")
        print(f"Full traceback:\n{error_traceback}")
        return jsonify({
            'error': str(e),
            'traceback': error_traceback
        }), 500

# ============================================================================
# SINGLE ACCESSION SEARCH ROUTE
# ============================================================================

search_sequencing_run_bp = Blueprint('search_sequencing_run_bp', __name__)

@search_sequencing_run_bp.route('/search_sequencing_run', methods=['POST'])
def search_sequencing_run():
    """
    Search for a single sequencing run by accession number.
    
    Request JSON:
        accession: SRA run accession (e.g., SRR123456)
        
    Returns:
        JSON with run details
    """
    accession = request.json.get('accession')
    if not accession:
        return jsonify({'error': 'Missing accession'}), 400
    
    sequencing_data = get_run_by_accession(accession)
    if not sequencing_data:
        return jsonify({'error': 'Run not found'}), 404

    return jsonify({'data': sequencing_data, 'status': 'success'}), 200
