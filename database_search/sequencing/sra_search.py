import pandas as pd
from pysradb.search import SraSearch


def search_sra_runs(organism, platform_config, size_limits, runs_blacklist):
    """
    Search SRA database for sequencing runs matching criteria.
    
    Args:
        organism: Scientific name or synonym
        platform_config: Dictionary with platform, layout, strategy, selection
        size_limits: Tuple (min_size, max_size) in base pairs
        runs_blacklist: Set of run accessions to exclude
        
    Returns:
        Pandas DataFrame with filtered and annotated runs, or None if no results
    """
    instance = SraSearch(
        organism=organism,
        return_max=200,
        source="GENOMIC",
        platform=platform_config['platform'],
        layout=platform_config['layout'],
        selection=platform_config.get('selection'),
        strategy=platform_config.get('strategy'),
        verbosity=3
    )
    
    instance.search()
    df = instance.get_df()
    
    if df.empty:
        return None
    
    # Select relevant columns
    columns_to_keep = [
        "study_accession", "experiment_accession", "experiment_library_strategy",
        "experiment_library_source", "experiment_library_selection", "sample_accession",
        "sample_alias", "experiment_instrument_model", "run_1_size", "run_1_total_spots",
        "experiment_alias", "experiment_design_description", "experiment_library_name",
        "experiment_platform", "experiment_sample_descriptor_accession", "library_layout",
        "run_1_alias", "run_1_base_A_count", "run_1_base_C_count", "run_1_base_G_count",
        "run_1_base_N_count", "run_1_base_T_count", "study_alias", "study_study_abstract",
        "study_study_title", "submission_center_name", "submission_lab_name", "run_1_accession",
        "sample_taxon_id", "sample_scientific_name", "experiment_title", "run_1_total_bases"
    ]
    
    # Filter and process data
    df = df.dropna(subset=['run_1_total_bases'])
    existing_columns = [col for col in columns_to_keep if col in df.columns]
    df = df[existing_columns]
    
    # Remove blacklisted runsa
    df = df[~df['run_1_accession'].isin(runs_blacklist)]
    
    # Convert size to GB and filter by size limits
    df['run_1_size'] = df['run_1_size'].astype(float) / (1024 ** 3)
    df['run_1_total_bases'] = df['run_1_total_bases'].astype(int)
    df = df[df['run_1_total_bases'] <= size_limits[1] * 2]

    # Sort by total bases and keep top 25
    df = df.sort_values(by='run_1_total_bases', ascending=False)[:25]
    
    # Rename columns to cleaner names
    df = rename_run_columns(df)
    
    # Detect HiFi runs for PacBio
    if 'platform' in df.columns and 'title' in df.columns:
        df['is_hifi'] = df.apply(
            lambda row: (
                row['platform'] == 'PACBIO_SMRT' and 
                isinstance(row.get('title'), str) and 
                'hifi' in row['title'].lower()
            ),
            axis=1
        )
    else:
        df['is_hifi'] = False
    
    return df


def rename_run_columns(df):
    """
    Rename DataFrame columns to more user-friendly names.
    
    Args:
        df: Pandas DataFrame with SRA run data
        
    Returns:
        DataFrame with renamed columns
    """
    column_mapping = {
        'run_1_accession': 'accession',
        'run_1_size': 'size',
        'run_1_total_bases': 'total_bases',
        'sample_taxon_id': 'taxid',
        'sample_scientific_name': 'scientific_name',
        'experiment_title': 'title',
        'experiment_platform': 'platform',
        'library_layout': 'layout',
        'experiment_library_strategy': 'strategy',
        'experiment_library_selection': 'selection'
    }  
    return df.rename(columns=column_mapping)


def get_run_by_accession(accession):
    """
    Fetch details for a specific run by accession number.
    
    Args:
        accession: SRA run accession (e.g., SRR123456)
        
    Returns:
        Dictionary with run details or None if not found
    """
    from pysradb.search import SraSearch
    
    instance = SraSearch(
        accession=accession,
        verbosity=3
    )
    instance.search()
    df = instance.get_df()
    
    if df.empty:
        return None
    
    # Select relevant columns
    columns_to_keep = [
        "study_accession", "experiment_accession", "experiment_library_strategy",
        "experiment_library_source", "experiment_library_selection", "sample_accession",
        "sample_alias", "experiment_instrument_model", "run_1_size", "run_1_total_spots",
        "experiment_alias", "experiment_design_description", "experiment_library_name",
        "experiment_platform", "experiment_sample_descriptor_accession", "library_layout",
        "run_1_alias", "run_1_base_A_count", "run_1_base_C_count", "run_1_base_G_count",
        "run_1_base_N_count", "run_1_base_T_count", "study_alias", "study_study_abstract",
        "study_study_title", "submission_center_name", "submission_lab_name", "run_1_accession",
        "sample_taxon_id", "sample_scientific_name", "experiment_title", "run_1_total_bases"
    ]
    
    existing_columns = [col for col in columns_to_keep if col in df.columns]
    df = df[existing_columns]
    
    # Convert size to GB
    df.loc[:, 'run_1_size'] = df['run_1_size'].apply(
        lambda x: float(x) / (1024 ** 3) if x is not None else None
    )
    
    # Rename columns
    df = rename_run_columns(df)

    if not df.empty:
        return df.iloc[0].to_dict()
    
    return None


def group_runs_by_taxid(runs):
    """
    Group runs by their taxonomy ID.
    
    Args:
        runs: List of run dictionaries
        
    Returns:
        Dictionary mapping taxid -> list of runs
    """
    species_dict = {}
    for run in runs:
        taxid = run['taxid']
        if taxid not in species_dict:
            species_dict[taxid] = []
        species_dict[taxid].append(run)
    return species_dict


def search_runs_for_species_simple(species_name, search_config, size_limits, runs_blacklist):
    """
    Simple search for runs with user-provided parameters only.
    
    Args:
        species_name: Scientific name or synonym
        search_config: Dictionary with platforms, layout, strategy, selection  
        size_limits: Tuple (min_size, max_size) in base pairs
        runs_blacklist: Set of run accessions to exclude from results
        
    Returns:
        List of run dictionaries
    """
    all_runs = []
    
    # Search each platform in the list
    for platform in search_config['platforms']:
        platform_config = {
            'platform': platform,
            'layout': search_config.get('layout'),
            'strategy': search_config.get('strategy'),
            'selection': search_config.get('selection')
        }
        
        df = search_sra_runs(species_name, platform_config, size_limits, runs_blacklist)
        
        if df is not None and not df.empty:
            new_runs = df.to_dict('records')
            all_runs.extend(new_runs)
            # Update blacklist with newly found accessions
            for run in new_runs:
                runs_blacklist.add(run['accession'])
    
    return all_runs
