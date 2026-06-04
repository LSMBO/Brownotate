import sys
import re
import pandas as pd
from pysradb.search import SraSearch


_LONG_READ_PLATFORMS = {'PACBIO_SMRT', 'OXFORD_NANOPORE'}


def _log(msg):
    """Flush-safe print so lines appear immediately in journalctl."""
    print(msg, flush=True)


def _to_int_or_none(value):
    if value is None:
        return None
    try:
        text = str(value).strip().replace(',', '')
        if text == '' or text.lower() == 'nan':
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def estimate_fastq_size_gb(total_bases, total_spots, layout, platform):
    """
    Estimate uncompressed FASTQ size in GiB from SRA metadata.

    Approximation:
    - Sequence + quality payload: ~2 bytes per base
    - Per-record overhead (headers/newlines): platform-dependent heuristic
    """
    bases = _to_int_or_none(total_bases)
    if not bases or bases <= 0:
        return None

    spots = _to_int_or_none(total_spots)
    layout_norm = str(layout or '').strip().upper()
    platform_norm = str(platform or '').strip().upper()
    is_long_read = platform_norm in _LONG_READ_PLATFORMS

    if spots and spots > 0:
        # For paired short reads, each spot usually yields two FASTQ records.
        if layout_norm == 'PAIRED' and not is_long_read:
            record_count = spots * 2
        else:
            record_count = spots
    else:
        # Fallback if spot count is missing.
        avg_read_len = 10000 if is_long_read else 150
        record_count = max(1, int(bases / avg_read_len))

    overhead_per_record = 40 if is_long_read else 70
    estimated_bytes = (2 * bases) + (record_count * overhead_per_record)
    return estimated_bytes / (1024 ** 3)


# Tissue-related attribute tag names (case-insensitive)
_TISSUE_TAGS = {
    'tissue', 'tissue_type', 'tissue type', 'organ', 'body_part', 'body part',
    'anatomical_part', 'anatomical part', 'cell_type', 'cell type',
    'source_name', 'biomaterial_type', 'tissue/organ',
}

# Values that carry no information
_NOINFO = {
    'n/a', 'na', 'none', 'not applicable', 'not collected',
    'not determined', 'unknown', 'missing', '-', '', 'na:',
    'unspecified', 'other', 'mixed',
}

# Keywords for text-mining fallback
_TISSUE_KEYWORDS = [
    'brain', 'liver', 'kidney', 'heart', 'lung', 'muscle', 'skin', 'blood',
    'spleen', 'testis', 'ovary', 'eye', 'gill', 'intestine', 'stomach',
    'pancreas', 'thymus', 'adipose', 'bone', 'cartilage', 'embryo',
    'larva', 'larvae', 'whole body', 'whole organism', 'gonad', 'mantle',
    'hepatopancreas', 'hemocyte', 'hemolymph', 'nerve', 'retina', 'antenna',
]


def extract_tissue_from_row(row, df_columns):
    """
    Extract tissue info from a pysradb DataFrame row.

    Strategy (in order of priority):
    1. sample_attributes_N_tag / _value pairs  (most reliable)
    2. experiment_attributes_N_tag / _value pairs
    3. Text-mining on free-text fields (title, alias, description)

    Returns a capitalised tissue string, or None.
    """
    try:
        # Build index of (prefix, N) pairs for both attribute families
        attr_pairs = []  # list of (tag_col, val_col)
        for prefix in ('sample_attributes', 'experiment_attributes'):
            indices = sorted(set(
                m.group(1)
                for col in df_columns
                for m in [re.match(rf'{prefix}_(\d+)_tag', col)]
                if m
            ), key=int)
            for n in indices:
                attr_pairs.append((f'{prefix}_{n}_tag', f'{prefix}_{n}_value'))

        # ── 1 & 2. Structured attributes ─────────────────────────────────
        for tag_col, val_col in attr_pairs:
            tag = row[tag_col] if tag_col in row.index else None
            val = row[val_col] if val_col in row.index else None
            if not isinstance(tag, str) or not isinstance(val, str):
                continue
            tag_lower = tag.strip().lower()
            val_stripped = val.strip()
            if tag_lower in _TISSUE_TAGS and val_stripped.lower() not in _NOINFO:
                _log(f"[RNAseq tissue]     structured hit [{tag_col}]: {tag!r} = {val_stripped!r}")
                return val_stripped[0].upper() + val_stripped[1:]

        # ── 3. Text-mining fallback on free-text fields ───────────────────
        text_fields = ['experiment_title', 'experiment_alias', 'sample_alias',
                       'sample_title', 'sample_description',
                       'experiment_design_description', 'experiment_library_name',
                       'pool_member_sample_title', 'pool_member_member_name']
        combined = ' '.join(
            str(row[f]) for f in text_fields
            if f in row.index and row[f] and str(row[f]).lower() not in ('nan', 'none', '')
        ).lower()

        for kw in _TISSUE_KEYWORDS:
            if kw in combined:
                _log(f"[RNAseq tissue]     text-mining hit: {kw!r}")
                return kw[0].upper() + kw[1:]

    except Exception as e:
        _log(f"[RNAseq tissue]   extract_tissue_from_row ERROR: {e}")

    return None


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
    
    # Keep SRA compressed size and expose estimated uncompressed FASTQ size.
    df['run_1_size'] = pd.to_numeric(df['run_1_size'], errors='coerce') / (1024 ** 3)
    df['run_1_sra_size'] = df['run_1_size']
    df['run_1_total_bases'] = df['run_1_total_bases'].astype(int)
    df['run_1_fastq_size_estimated_gb'] = df.apply(
        lambda row: estimate_fastq_size_gb(
            row.get('run_1_total_bases'),
            row.get('run_1_total_spots'),
            row.get('library_layout'),
            row.get('experiment_platform')
        ),
        axis=1,
    )
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
        'run_1_fastq_size_estimated_gb': 'size',
        'run_1_sra_size': 'sra_size',
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
    
    # Keep SRA compressed size and expose estimated uncompressed FASTQ size.
    df.loc[:, 'run_1_size'] = pd.to_numeric(df['run_1_size'], errors='coerce') / (1024 ** 3)
    df.loc[:, 'run_1_sra_size'] = df['run_1_size']
    df.loc[:, 'run_1_fastq_size_estimated_gb'] = df.apply(
        lambda row: estimate_fastq_size_gb(
            row.get('run_1_total_bases'),
            row.get('run_1_total_spots'),
            row.get('library_layout'),
            row.get('experiment_platform')
        ),
        axis=1,
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


def search_rna_runs_for_species(
    species_name,
    platforms,
    layout,
    runs_blacklist,
    min_run_size_gb=None,
    max_run_size_gb=None,
):
    """
    Search SRA for RNA-seq runs for a given species.

    Args:
        species_name: Scientific name or synonym
        platforms: List of platform names
        layout: Layout type ('PAIRED', 'SINGLE', or None for any)
        runs_blacklist: Set of run accessions to exclude

    Returns:
        List of run dictionaries
    """
    all_runs = []

    for platform in platforms:
        _log(f"[RNAseq tissue] Searching platform={platform} organism={species_name!r} layout={layout!r}")
        instance = SraSearch(
            organism=species_name,
            return_max=200,
            source="TRANSCRIPTOMIC",
            platform=platform if platform != 'any' else None,
            layout=layout if layout and layout != 'any' else None,
            strategy="RNA-Seq",
            verbosity=3
        )
        instance.search()
        df = instance.get_df()

        if df is None or df.empty:
            _log(f"[RNAseq tissue]   → No results for platform={platform}")
            continue

        _log(f"[RNAseq tissue]   → {len(df)} raw rows. Columns: {list(df.columns)}")

        # Columns we always want
        base_columns = [
            "study_accession", "experiment_accession", "experiment_library_strategy",
            "experiment_library_source", "experiment_library_selection", "sample_accession",
            "sample_alias", "experiment_instrument_model", "run_1_size", "run_1_total_spots",
            "experiment_alias", "experiment_design_description", "experiment_library_name",
            "experiment_platform", "experiment_sample_descriptor_accession", "library_layout",
            "run_1_alias", "run_1_accession", "sample_taxon_id", "sample_scientific_name",
            "experiment_title", "run_1_total_bases",
            "pool_member_sample_title", "pool_member_member_name",
        ]

        # Keep all sample_attributes_N and experiment_attributes_N cols for tissue extraction
        attr_cols = [c for c in df.columns if re.match(r'(sample|experiment)_attributes_\d+_(tag|value)', c)]
        _log(f"[RNAseq tissue]   → attribute cols found: {attr_cols}")

        columns_to_keep = base_columns + attr_cols
        existing_columns = [col for col in columns_to_keep if col in df.columns]
        df = df.dropna(subset=['run_1_total_bases'])
        df = df[existing_columns]
        df = df[~df['run_1_accession'].isin(runs_blacklist)]

        df['run_1_total_bases'] = df['run_1_total_bases'].astype(int)
        if 'run_1_size' in df.columns:
            df['run_1_size'] = pd.to_numeric(df['run_1_size'], errors='coerce') / (1024 ** 3)
            df['run_1_sra_size'] = df['run_1_size']
        else:
            df['run_1_sra_size'] = None

        df['run_1_fastq_size_estimated_gb'] = df.apply(
            lambda row: estimate_fastq_size_gb(
                row.get('run_1_total_bases'),
                row.get('run_1_total_spots'),
                row.get('library_layout'),
                row.get('experiment_platform')
            ),
            axis=1,
        )

        # Optional per-run size filter in GB uses estimated FASTQ size.
        if min_run_size_gb is not None:
            df = df[df['run_1_fastq_size_estimated_gb'] >= float(min_run_size_gb)]
        if max_run_size_gb is not None:
            df = df[df['run_1_fastq_size_estimated_gb'] <= float(max_run_size_gb)]

        if df.empty:
            _log(f"[RNAseq tissue]   → No runs after size filter (min={min_run_size_gb}, max={max_run_size_gb})")
            continue

        # Extract tissue before renaming (need original col names for attr extraction)
        _log(f"[RNAseq tissue]   → Extracting tissue for {len(df)} rows...")
        df['tissue'] = df.apply(lambda row: extract_tissue_from_row(row, df.columns), axis=1)
        tissue_summary = df[['run_1_accession', 'tissue']].to_dict('records')
        _log(f"[RNAseq tissue]   → Tissue results: {tissue_summary}")

        # Drop attribute columns before final rename/export
        df = df.drop(columns=attr_cols, errors='ignore')
        df = rename_run_columns(df)

        new_runs = df.to_dict('records')
        all_runs.extend(new_runs)
        for run in new_runs:
            runs_blacklist.add(run['accession'])

    return all_runs
