import subprocess
import json
import os
from flask_app.utils import load_config


# Load configuration
config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


def fetch_ncbi_genome_assemblies(taxid):
    """
    Fetch genome assembly information from NCBI for a given taxid.
    
    Uses the NCBI datasets command-line tool to retrieve assembly statistics.
    
    Args:
        taxid: NCBI taxonomy ID
        
    Returns:
        List of genome assembly reports, or empty list if none found
    """
    command = [
        "datasets",
        "summary",
        "genome",
        "taxon", str(taxid),
        "--assembly-level", "chromosome,complete,scaffold",
        "--limit", "10000",
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
        return json.loads(result.stdout).get("reports", [])
    except FileNotFoundError:
        print("Error: 'datasets' command-line tool is not installed or not in PATH.")
        return []
    except subprocess.CalledProcessError as e:
        print(f"Error: Command failed with error {e}")
        return []


def calculate_genome_size_stats(assembly_reports, coverage_lower=50, coverage_upper=80):
    """
    Calculate genome size statistics from assembly reports.
    
    Args:
        assembly_reports: List of NCBI assembly report dictionaries
        coverage_lower: Minimum coverage for calculating lower_bound
        coverage_upper: Maximum coverage for calculating upper_bound
        
    Returns:
        Dictionary with 'mean', 'lower_bound', 'upper_bound' or None if no valid data
    """
    sizes = []
    for report in assembly_reports:
        if 'assembly_stats' in report and 'total_sequence_length' in report['assembly_stats']:
            size_value = report['assembly_stats']['total_sequence_length']
            try:
                sizes.append(int(size_value))
            except (ValueError, TypeError):
                continue
    
    if not sizes:
        return None
    
    mean = sum(sizes) / len(sizes)
    return {
        'mean': mean,
        'lower_bound': mean * coverage_lower,
        'upper_bound': mean * coverage_upper
    }


def estimate_genome_size(taxonomy, coverage_lower=50, coverage_upper=80):
    """
    Estimate genome size by searching through taxonomy lineage.
    
    Strategy:
    1. Try the input species first
    2. If not found, search through taxonomic lineage (genus, family, etc.)
    3. Return the first valid genome size found
    4. If nothing found, use default values (1 Gbp genome)
    
    Args:
        taxonomy: Taxonomy dictionary with taxonId and lineage information
        coverage_lower: Minimum coverage for calculating lower_bound (default: 50)
        coverage_upper: Maximum coverage for calculating upper_bound (default: 80)
        
    Returns:
        Dictionary with genome size statistics (mean, lower_bound, upper_bound)
    """
    # Try input species first
    results = fetch_ncbi_genome_assemblies(taxonomy['taxonId'])
    if results:
        stats = calculate_genome_size_stats(results, coverage_lower, coverage_upper)
        if stats:
            return stats
    
    # Search through lineage (genus, family, order, etc.)
    for taxo in taxonomy.get("lineage", []):
        results = fetch_ncbi_genome_assemblies(taxo["taxonId"])
        if results:
            stats = calculate_genome_size_stats(results, coverage_lower, coverage_upper)
            if stats:
                return stats
    
    # Fallback to default values if no genome size found
    print(f"Warning: Could not estimate genome size for {taxonomy['scientificName']}")
    mean_size = 1e9  # 1 Gbp default
    return {
        'mean': mean_size,
        'lower_bound': mean_size * coverage_lower,
        'upper_bound': mean_size * coverage_upper
    }


def format_genome_size_for_canu(genome_size_bp):
    """
    Format genome size in base pairs to CANU-compatible string format.
    
    CANU accepts genome size with suffixes: k (kilobase), m (megabase), g (gigabase)
    
    Args:
        genome_size_bp: Genome size in base pairs (int or float)
        
    Returns:
        String formatted for CANU (e.g., "12m", "1.5g", "500k")
    """
    if genome_size_bp >= 1e9:
        # Gigabases (Gb)
        size_gb = genome_size_bp / 1e9
        # Round to 1 decimal place if not a whole number
        if size_gb == int(size_gb):
            return f"{int(size_gb)}g"
        else:
            return f"{size_gb:.1f}g"
    elif genome_size_bp >= 1e6:
        # Megabases (Mb)
        size_mb = genome_size_bp / 1e6
        if size_mb == int(size_mb):
            return f"{int(size_mb)}m"
        else:
            return f"{size_mb:.1f}m"
    else:
        # Kilobases (Kb)
        size_kb = genome_size_bp / 1e3
        if size_kb == int(size_kb):
            return f"{int(size_kb)}k"
        else:
            return f"{size_kb:.1f}k"
