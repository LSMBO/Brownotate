import os
import pandas as pd
from itertools import combinations
from utils import load_config
from pysradb.search import SraSearch
import statistics
import subprocess
import json
from flask import Blueprint, request, jsonify
from flask_app.database import find, update_one
from timer import timer
import database_search.ncbi as ncbi

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']

platforms_layout_tuples = [("ILLUMINA", "PAIRED"), ("ILLUMINA", "SINGLE"), ("BGISEQ", "PAIRED"), ("BGISEQ", "SINGLE"), ("ION_TORRENT", "SINGLE")]
extra_platforms_layout_tuples = platforms_layout_tuples + [
    ("OXFORD_NANOPORE", None), ("PACBIO_SMRT", None), ("CAPILLARY", None),
    ("ABI_SOLID", None), ("LS454", None), ("COMPLETE_GENOMICS", None), ("HELICOS", None)
]

search_sequencing_run_bp = Blueprint('search_sequencing_run_bp', __name__)

@search_sequencing_run_bp.route('/search_sequencing_run', methods=['POST'])
def search_sequencing_run():
    accession = request.json.get('accession')
    if not accession:
        return jsonify({"error": "Accession number is required"}), 400
    sequencing_data = get_accession(accession)
    if not sequencing_data:
        return jsonify({"error": "No data found for the given accession number"}), 404
    return jsonify({'data': sequencing_data, 'status': 'success'}), 200



dbs_dnaseq_bp = Blueprint('dbs_dnaseq_bp', __name__)

@dbs_dnaseq_bp.route('/dbs_dnaseq', methods=['POST'])
def dbs_dnaseq():
    start_time = timer.start()
    
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')
    restricted = request.json.get('restricted')
    
    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'dnaseq',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }

    dnaseq = get_dnaseq(output_data['data'], restricted)
    output_data['data']['dnaseq'] = dnaseq

    timer_str = timer.stop(start_time)
    print(f"Timer dbs_dnaseq: {timer_str}")
    output_data['data']['timer_dnaseq'] = timer_str

    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'dnaseq', 'data': output_data['data']} } 
        
    if create_new_dbs:
        update_one('dbsearch', query, update)

    return jsonify(output_data)

def fetch_ncbi_genomes(taxid):
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
    
    
def get_genome_size(taxonomy):
    for taxo in taxonomy["lineage"]:
        results = fetch_ncbi_genomes(taxo["taxonId"])
        if results:
            genome_sizes = []
            species_list = []
            for res in results:
                length = int(res['assembly_stats']['total_sequence_length'])
                species_name = res['organism']['organism_name']
                if species_name not in species_list:
                    genome_sizes.append(length)
                    species_list.append(species_name)
                    
            mean  = round(statistics.mean(genome_sizes)) if genome_sizes else 0
            std   = round(statistics.stdev(genome_sizes)) if len(genome_sizes) > 1 else 0
            cv = std / mean if mean > 0 else 0
            lower_bound = mean * 50
            upper_bound = mean * 80
            return {
                'min': min(genome_sizes) if genome_sizes else 0,
                'max': max(genome_sizes) if genome_sizes else 0,
                'mean': mean,
                'std': std,
                'cv': round(cv, 3),
                'count': len(genome_sizes),
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'taxid': taxo["taxonId"],
                'scientific_name': taxo["scientificName"],
                'species_list': species_list
            }            
        
    return None

def run_pysradb(command, size_limits, runs_blacklist):
    instance = SraSearch(
        organism=command['organism'],
        return_max=200,
        source="GENOMIC",
        platform=command['platform'],
        layout=command['layout'],
        selection=command['selection'],
        strategy=command['strategy'],
        verbosity=3
    )
    instance.search()
    original_df = instance.get_df()
    if original_df.empty:
        return None
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
    df = original_df.dropna(subset=['run_1_total_bases'])
    existing_columns = [col for col in columns_to_keep if col in df.columns]
    df = df[existing_columns]
    df = df[~df['run_1_accession'].isin(runs_blacklist)]
    df['run_1_size'] = df['run_1_size'].astype(float) / (1024 ** 3)
    df['run_1_total_bases'] = df['run_1_total_bases'].astype(int)
    df = df[df['run_1_total_bases'] < size_limits[1] * 2]        
        
    df = df.sort_values(by='run_1_total_bases', ascending=False)
    df = rename_columns(df)
    df['optimal_platform'] = df['platform'].apply(lambda x: x in ['ILLUMINA', 'BGISEQ', 'ION_TORRENT'])
    df['optimal_strategy'] = df['strategy'] == 'WGS'
    df['optimal_selection'] = df['selection'] == 'RANDOM'
    return df

def rename_columns(df):
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


def fetch_runs_for_species(species, parameters):
    size_limits = parameters['original_size_limits']
    selection = parameters['selection']
    strategy = parameters['strategy']
    runs_blacklist = parameters['runs_blacklist']
    runs = []
    if selection:
        platforms_layouts = platforms_layout_tuples
    else:
        platforms_layouts = extra_platforms_layout_tuples
    
    for platform, layout in platforms_layouts:
        command = {
            "organism": species,
            "platform": platform,
            "layout": layout,
            "selection": selection,
            "strategy": strategy
        }
        df = run_pysradb(command, size_limits, runs_blacklist)
        if df is not None and not df.empty:
            runs.extend(df.to_dict(orient='records'))
            
        if parameters['exclude_input_species']:
            runs = [run for run in runs if run['taxid'] != str(parameters['input_taxid'])]
    return runs

def group_runs_by_species(runs):
    species_dict = {}
    for run in runs:
        taxid = run['taxid']
        if taxid not in species_dict:
            species_dict[taxid] = []
        species_dict[taxid].append(run)
    return species_dict

def find_batches_for_input_taxonomy(parameters):
    input_taxid = parameters['taxonomy']['taxonId']
    lineage = parameters['taxonomy']['lineage']
    
    get_all_batches_parameters = {
        'input_taxid': input_taxid,
        'taxonomy': parameters['taxonomy'],
        'selection': "RANDOM",
        'strategy': "WGS",
        'original_size_limits': parameters['size_limit'],
        'runs_blacklist': set(),
        'max_batch_count': parameters['max_batch_count'],
        'optimal_only': False,
        'exclude_input_species': False,
    }
    
    get_all_batches_no_strategy_parameters = get_all_batches_parameters.copy()
    get_all_batches_no_strategy_parameters['selection'] = None
    get_all_batches_no_strategy_parameters['strategy'] = None    
    
    if len(parameters['all_batches']) < parameters['max_batch_count']:
        batches, runs_blacklist = get_all_batches(get_all_batches_parameters, expanded=True)
        parameters['all_batches'].extend(batches)
        get_all_batches_parameters['runs_blacklist'].update(runs_blacklist)
        get_all_batches_no_strategy_parameters['runs_blacklist'].update(runs_blacklist)
    if len(parameters['all_batches']) < parameters['max_batch_count']:
        batches, runs_blacklist = get_all_batches(get_all_batches_no_strategy_parameters, expanded=True)
        parameters['all_batches'].extend(batches)        
        get_all_batches_parameters['runs_blacklist'].update(runs_blacklist)
        get_all_batches_no_strategy_parameters['runs_blacklist'].update(runs_blacklist)
    return prioritize_batches(parameters['all_batches'], input_taxid, parameters['max_batch_count'], parameters['genome_size'])

def find_batches_along_lineage(parameters):
    input_taxid = parameters['taxonomy']['taxonId']
    lineage = parameters['taxonomy']['lineage']
    
    get_all_batches_parameters = {
        'input_taxid': input_taxid,
        'taxonomy': parameters['taxonomy'],
        'selection': "RANDOM",
        'strategy': "WGS",
        'original_size_limits': parameters['size_limit'],
        'runs_blacklist': set(),
        'max_batch_count': parameters['max_batch_count'],
        'optimal_only': False,
        'exclude_input_species': False,
    }
    
    get_all_batches_no_strategy_parameters = get_all_batches_parameters.copy()
    get_all_batches_no_strategy_parameters['selection'] = None
    get_all_batches_no_strategy_parameters['strategy'] = None
    
    max_batch_count = parameters['max_batch_count']
    
    for taxo in lineage:
        get_all_batches_parameters['taxonomy'] = taxo
        if (len(parameters['all_batches']) < max_batch_count) or not (any(batch['optimal_sequencing_set'] for batch in parameters['all_batches'])):
            batches, runs_blacklist = get_all_batches(get_all_batches_parameters, expanded=True)
            parameters['all_batches'].extend(batches)
            get_all_batches_parameters['runs_blacklist'].update(runs_blacklist)
            
        if (len(parameters['all_batches']) < max_batch_count) or not (any(batch['optimal_sequencing_set'] for batch in parameters['all_batches'])):
            alt_batches, runs_blacklist = get_all_batches(get_all_batches_no_strategy_parameters, expanded=True)
            parameters['all_batches'].extend(alt_batches)
            get_all_batches_parameters['runs_blacklist'].update(runs_blacklist)
        if any(batch['optimal_sequencing_set'] for batch in parameters['all_batches']):
            break
    return prioritize_batches(parameters['all_batches'], input_taxid, max_batch_count, parameters['genome_size'])

def get_batches_for_species(parameters):
    min_size, max_size = parameters['new_size_limits']
    original_min_size, original_max_size = parameters['original_size_limits']
    max_batch_size = 8    
    runs = [run for run in parameters['runs'] if run['total_bases'] <= max_size]

    runs = sorted(runs, key=lambda r: r['total_bases'], reverse=True)[:25]

    batches = []
    
    for run in runs:
        print(run['accession'], run['total_bases'], run['size'], run['taxid'], run['scientific_name'], run['strategy'], run['selection'])

    if min_size == 0 and runs:
        batch = []
        total_size_bases = 0
        for run in runs:
            if total_size_bases < max_size and run['accession'] not in parameters['runs_blacklist']:
                batch.append(run)
                total_size_bases += run['total_bases']
            else:
                break
            batch_accessions = [run['accession'] for run in batch]
            
            total_size_gb = sum(run['size'] for run in batch)
            batches.append({
                "runs": batch,
                "total_size_bases": total_size_bases,
                "total_size_gb": total_size_gb,
                "taxid": batch[0]['taxid'],
                "scientific_name": batch[0]['scientific_name'],
                "optimal_sequencing_set": False,
                "optimal_size": 0,
            })
            parameters['runs_blacklist'].update(batch_accessions)
            
            return batches, parameters['runs_blacklist']

    for batch_size in range(1, max_batch_size + 1):
        for batch in combinations(runs, batch_size):
            batch_accessions = [run['accession'] for run in batch]
            if any(accession in parameters['runs_blacklist'] for accession in batch_accessions):
                continue
            total_size_bases = sum(run['total_bases'] for run in batch)
            total_size_gb = sum(run['size'] for run in batch)

            optimal_size = 1
            if original_min_size <= total_size_bases <= original_max_size:
                optimal_size = 2

            all_classic = all(run["strategy"] == 'WGS' and run["selection"] == 'RANDOM' for run in batch)
            is_optimal = optimal_size == 2 and all_classic
            if min_size <= total_size_bases <= max_size and (not parameters['optimal_only'] or is_optimal):
                batches.append({
                    "runs": batch,
                    "total_size_bases": total_size_bases,
                    "total_size_gb": total_size_gb,
                    "taxid": batch[0]['taxid'],
                    "scientific_name": batch[0]['scientific_name'],
                    "optimal_sequencing_set": is_optimal,
                    "optimal_size": optimal_size,
                })
                parameters['runs_blacklist'].update(batch_accessions)
                if len(batches) >= parameters['max_batch_count']:
                    return batches, parameters['runs_blacklist']

    return batches, parameters['runs_blacklist']

def get_all_batches(parameters, expanded):
    synonyms = [parameters['taxonomy']['scientificName']] + parameters['taxonomy'].get('synonyms', [])
    all_runs = []
    # 1. Search for the input species and its synonyms
    for species in synonyms:
        all_runs.extend(fetch_runs_for_species(species, parameters))

    # 2. Generate batches for each species found
    selected_batches = []
    species_dict = group_runs_by_species(all_runs)
    get_batches_for_species_parameters = {
        'runs': [],
        'original_size_limits': parameters['original_size_limits'],
        'new_size_limits': parameters['original_size_limits'],
        'runs_blacklist': parameters['runs_blacklist'],
        'max_batch_count': parameters['max_batch_count'],
        'optimal_only': parameters['optimal_only']
    }
    for taxid, runs in species_dict.items():
        get_batches_for_species_parameters['runs'] = runs
        batches, parameters['runs_blacklist'] = get_batches_for_species(get_batches_for_species_parameters)
        selected_batches.extend(batches)
        if len(selected_batches) >= parameters['max_batch_count']:
            return selected_batches, parameters['runs_blacklist']

    if expanded:
        for new_size_limits in [(parameters['original_size_limits'][0] * 0.5, parameters['original_size_limits'][1] * 1.5), (0, parameters['original_size_limits'][1] * 2)]:
            new_min = new_size_limits[0]
            new_max = new_size_limits[1]
            for taxid, runs in species_dict.items():
                get_batches_for_species_parameters['runs'] = runs
                get_batches_for_species_parameters['new_size_limits'] = (new_min, new_max)
                batches, parameters['runs_blacklist'] = get_batches_for_species(get_batches_for_species_parameters)
                selected_batches.extend(batches)
                if len(selected_batches) >= parameters['max_batch_count']:
                    return selected_batches, parameters['runs_blacklist']
                
    return selected_batches, parameters['runs_blacklist']

    
def prioritize_batches(batches, input_taxid, max_batch_count, genome_size):
    # Batches of the input species first (even if not optimal)
    input_batches = [batch for batch in batches if batch['taxid'] == str(input_taxid)]
    other_batches = [batch for batch in batches if batch['taxid'] != str(input_taxid)]
    
    # Sort each group to prioritize optimal ones first
    input_batches = sorted(input_batches, key=lambda x: not x['optimal_sequencing_set'])
    other_batches = sorted(other_batches, key=lambda x: not x['optimal_sequencing_set'])
    sorted_batches = input_batches + other_batches
    
    # Ensure there is at least one optimal batch in the final selection
    final_batches = sorted_batches[:max_batch_count]
    if not any(batch['optimal_sequencing_set'] for batch in final_batches):
        for batch in sorted_batches:
            if batch['optimal_sequencing_set']:
                final_batches[-1] = batch
                break
    for batch in final_batches:
        batch['assembly_expected_size'] = genome_size['mean']
        batch['assembly_expected_size_stats'] = genome_size
    return final_batches

def get_dnaseq(data, restricted, max_batch_count=5):
    taxonomy = data['taxonomy']
    genome_size = get_genome_size(taxonomy)
    size_limit = [genome_size['lower_bound'], genome_size['upper_bound']]
    
    find_batches_parameters = {
        "taxonomy": taxonomy,
        "size_limit": size_limit,
        "genome_size": genome_size,
        "all_batches": [],
        "max_batch_count": max_batch_count
    }
    
    if restricted:
        return find_batches_for_input_taxonomy(find_batches_parameters)
    
    if 'dnaseq' in data:
        find_batches_parameters['all_batches'] = data['dnaseq']

    return find_batches_along_lineage(find_batches_parameters)

def get_accession(accession):
    instance = SraSearch(
        accession=accession,
        verbosity=3
    )
    instance.search()
    df = instance.get_df()
    if df.empty:
        return None
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
    df.loc[:, 'run_1_size'] = df['run_1_size'].apply(lambda x: float(x) / (1024 ** 3) if pd.notna(x) else None)
    df = rename_columns(df)
    df['optimal_platform'] = df['platform'].apply(lambda x: x in ['ILLUMINA', 'BGISEQ', 'ION_TORRENT'])
    df['optimal_strategy'] = df['strategy'] == 'WGS'
    df['optimal_selection'] = df['selection'] == 'RANDOM'
    if df is not None and not df.empty:
        return df.iloc[0].to_dict()
    return None
            
