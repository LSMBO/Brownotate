from database_search.uniprot import UniprotTaxo
import requests
import time
import os
import subprocess
import json
import matplotlib.pyplot as plt
from utils import load_config
from ftp import ensembl
from .sra import getBetterSra

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


def create_taxo(taxid, reference_taxid=None):
    return UniprotTaxo(taxid, reference_taxid)

def get_uniprot_swissprot(taxo):
    return taxo.search_swissprot_data()

def get_uniprot_trembl(taxo):
    return taxo.search_trembl_data()

def get_uniprot_proteomes(data):
    proteomes = []
    exclude_ids = []
    for taxo in data['taxonomy']['lineage']:
        if taxo['rank'] == "strain":
            proteomes += search_proteome(taxo['taxonId'])
        elif taxo['rank'] == "species":
            proteomes += search_proteome(taxo['taxonId'])
        else:
            children = get_children(taxo['taxonId'], exclude_ids)
            children_taxids, children_scientific_names = zip(*children) if children else ([], [])
            exclude_ids += children_taxids
            for child in children_taxids:
                proteomes += search_proteome(child)
                if len(proteomes) == 3:
                    return proteomes

        if proteomes:
            return proteomes

def search_proteome(taxid):
    url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{taxid})&size=500&format=json"
    response = requests_get(url)
    proteomes = []
    if response and response.json()["results"]:
        results = response.json()["results"]
        proteome_count = 0
        for result in results:
            if proteome_count == 3:
                return proteomes
            proteome_type = result["proteomeType"]
            proteomes.append({
                "database": "uniprot",
                "data_type": "uniprot_proteome",
                "data_type": "proteins",
                "accession": result["id"],
                "proteome_type": proteome_type,
                "scientific_name": result["taxonomy"]["scientificName"],
                "taxid": result["taxonomy"]["taxonId"],
                "download_url": f"https://rest.uniprot.org/uniprotkb/stream?query=proteome:{result['id']}&format=fasta",
                "url": f"https://www.uniprot.org/proteomes/{result['id']}"
            })
            proteome_count += 1
    return proteomes

   
def get_children(taxid, exclude_ids=[]):
    childs = []
    url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxid})%20AND%20(rank:SPECIES%20OR%20rank:STRAIN%20OR%20rank:SUBSPECIES)&size=500&format=json"
    response = get_url(url)
    results = response.json()["results"]       
    for result in results:
        child_taxon_id = result['taxonId']
        proteome_count = result['statistics']['proteomeCount']
        if proteome_count > 0 and child_taxon_id not in exclude_ids:
            childs.append((result['taxonId'], result['scientificName']))
        if len(childs) >= 3:
            return childs
    while response.links.get("next", {}).get("url"):
        response = get_url(response.links["next"]["url"])
        results = response.json()["results"]
        for result in results:
            child_taxon_id = result["taxonId"]
            proteome_count = result['statistics']['proteomeCount']
            if proteome_count > 0 and child_taxon_id not in exclude_ids:
                childs.append((result['taxonId'], result['scientificName']))
            if len(childs) >= 3:
                return childs
    return childs

def get_ncbi_genomes(data, assembly_source, limit=3):
    annotated_genomes = []
    genomes = []
    output_annotated_genomes = []
    output_genomes = []
    for taxo in data['taxonomy']['lineage']:
        for level in ["chromosome", "complete", "scaffold", "contig"]:
            if len(annotated_genomes) >= limit:
                break
            results = fetch_ncbi_genomes(taxo['taxonId'], assembly_source, level, True, limit-len(genomes))
            annotated_genomes += results
            genomes += results
        
        if len(genomes) < limit:
            for level in ["chromosome", "complete", "scaffold", "contig"]:
                if len(genomes) >= limit:
                    break
                results = fetch_ncbi_genomes(taxo['taxonId'], assembly_source, level, False, limit)
                for result in results:
                    if result not in genomes:
                        genomes.append(result)
        
        if annotated_genomes and not output_annotated_genomes:
            for annotated_genome in annotated_genomes:
                if "busco" in annotated_genome["annotation_info"]:
                    busco = round(100 * (annotated_genome["annotation_info"]["busco"]["complete"] + annotated_genome["annotation_info"]["busco"]["duplicated"]))
                else:
                    busco = None
                accession = annotated_genome["accession"]
                download_command = ["datasets", "download", "genome", "accession", accession, "--filename", f"{accession}_annotation.zip", "--include", "protein"]
                output_annotated_genomes.append({
                    "database": "ncbi",
                    "accession": accession,
                    "data_type": f"ncbi_{assembly_source}_proteins",
                    "scientific_name": annotated_genome["organism"]["organism_name"],
                    "taxid": annotated_genome["organism"]["tax_id"],
                    "busco": f"{busco}%",
                    "download_command": download_command,
                    'url': f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/"
                })
            
        if genomes and not output_genomes:
            for genome in genomes:
                accession = genome["accession"]
                download_command = ["datasets", "download", "genome", "accession", accession, "--filename", f"{accession}_assembly.zip", "--include", "genome"]
                output_genomes.append({
                    "database": "ncbi",
                    "accession": accession,
                    "data_type": f"ncbi_{assembly_source}_genome",
                    "scientific_name": genome["organism"]["organism_name"],
                    "taxid": genome["organism"]["tax_id"],
                    "assembly_level": genome["assembly_info"]["assembly_level"],
                    "download_command": download_command,
                    'url': f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/"
                })
        
        if output_annotated_genomes and output_genomes:
            return output_annotated_genomes, output_genomes
        
    return output_annotated_genomes, output_genomes


def fetch_ncbi_genomes(taxid, assembly_source, assembly_level, annotated, limit):
    command = [
        "datasets", "summary", "genome", "taxon", str(taxid),
        "--assembly-source", assembly_source,
        "--assembly-level", assembly_level,
    ]
    if annotated:
        command.append("--annotated")
    command += ["--limit", str(limit)]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, env=env
        )
        return json.loads(result.stdout).get("reports", [])
    
    except subprocess.CalledProcessError as e:
        return []


def get_ensembl(data):
    for taxo in data['taxonomy']['lineage']:
        if taxo['scientificName'] == "Bacteria" or taxo['scientificName'] == "Archaea" or taxo['scientificName'] == "Viridiplantae":
            return [], []
        if taxo['scientificName'] == "Fungi":
            assembly, proteins = ensembl.getDataFromFTP('saccharomyces_cerevisiae', 4932)
            return [assembly], [proteins]
        if taxo['scientificName'] == "Arthropoda":
            assembly, proteins = ensembl.getDataFromFTP('drosophila_melanogaster', 7227)
            return [assembly], [proteins]
        
    ensembl_ftp_species = ensembl.ensembl_species
    is_group = False
    if data['taxonomy']['lineage'][0]['rank'] not in ['species', 'subspecies', 'strain']:
        is_group = True
    exclude_ids = []
    output_assemblies = []
    output_proteins = []
    
    for taxo in data['taxonomy']['lineage']:
        if taxo['rank'] == 'genus':
            is_group = True
        
        if is_group:
            children = get_children(taxo['taxonId'], exclude_ids)
            children_taxids, children_scientific_names = zip(*children) if children else ([], [])
            exclude_ids += children_taxids

            for child in children:
                taxid = child[0]
                formated_name = child[1].replace(" ", "_").lower()
                if formated_name in ensembl_ftp_species:
                    assemblies, proteins = ensembl.getDataFromFTP(formated_name, taxid)
                    output_assemblies.append(assemblies)
                    output_proteins.append(proteins)
            if output_assemblies and output_proteins:
                return output_assemblies, output_proteins
            
        else:
            formated_name = taxo["scientificName"].replace(" ", "_").lower()
            if formated_name in ensembl_ftp_species:
                assembly, proteins = ensembl.getDataFromFTP(formated_name, taxo['taxonId'])
                return [assembly], [proteins]
        
    return output_assemblies, output_proteins

def get_dnaseq(data):
    taxonomy = data['taxonomy']
    synonyms_scientific_names = [taxonomy['scientificName']]
    if 'synonyms' in taxonomy.keys():
        synonyms_scientific_names += taxonomy['synonyms']

    return getBetterSra(synonyms_scientific_names, taxonomy, "DNA", config, illumina_only=True, sra_blacklist=[])
        
def get_phylogeny_map(dbsearch, output_path):
    main_lineage = dbsearch['taxonomy']['lineage']
    list_of_taxid = []
    for entry in dbsearch['uniprot_proteomes']:
        list_of_taxid.append(entry['taxid'])
    for entry in dbsearch['ncbi_refseq_annotated_genomes']:
        list_of_taxid.append(entry['taxid'])
    for entry in dbsearch['ncbi_genbank_annotated_genomes']:
        list_of_taxid.append(entry['taxid'])
    for entry in dbsearch['ncbi_refseq_genomes']:
        list_of_taxid.append(entry['taxid'])
    for entry in dbsearch['ncbi_genbank_genomes']:
        list_of_taxid.append(entry['taxid'])                        
    for entry in dbsearch['ensembl_annotated_genomes']:
        list_of_taxid.append(entry['taxid'])
    for entry in dbsearch['ensembl_genomes']:
        list_of_taxid.append(entry['taxid'])   
    for entry in dbsearch['dnaseq']['runs']:
        list_of_taxid.append(int(entry['taxid']))
    list_of_taxid = list(set(list_of_taxid))
    list_of_lineage = []
    for taxid in list_of_taxid:
        if taxid != dbsearch['taxonomy']['taxonId']:
            taxo = create_taxo(taxid, dbsearch['taxonomy']['taxonId'])
            if taxo:
                list_of_lineage.append(taxo.taxonomy['lineage'])

    fig, ax = plt.subplots(figsize=(10, 5))
    
    main_lineage_taxids = [entry['taxonId'] for entry in main_lineage]
    main_lineage_scientific_names = [entry['scientificName'] for entry in main_lineage]
    main_lineage_ranks = [entry['rank'] for entry in main_lineage]
    main_lineage_string = f"{main_lineage_scientific_names[0]} ({main_lineage_ranks[0]}) TaxID: {main_lineage_taxids[0]}"
    
    ylim = len(main_lineage_taxids)
    y_main = range(len(main_lineage_taxids))
    x_main = range(len(main_lineage_taxids))
    ax.plot(x_main, y_main, linestyle='-', color='black', marker='o')

    intersection_indexes = []
    for lineage in list_of_lineage:
        lineage_taxids = [entry['taxonId'] for entry in lineage]
        lineage_scientific_names = [entry['scientificName'] for entry in lineage]
        lineage_ranks = [entry['rank'] for entry in lineage]
        taxo_string = f"{lineage_scientific_names[0]} ({lineage_ranks[0]}) TaxID: {lineage_taxids[0]}"

        intersection_index = get_phylogeny_intersection(lineage_taxids, main_lineage_taxids)
        intersection_indexes.append(intersection_index)
        if intersection_index > 0:
            x_lineage = [intersection_index, 0]
            y_lineage = [intersection_index, 2 * intersection_index]
            ax.plot(x_lineage, y_lineage, linestyle='-', color='green', marker='o')
            if ylim < (2 * intersection_index) + 1:
                ylim = (2 * intersection_index) + 1
            for j, (name, rank, taxid) in enumerate(zip(main_lineage_scientific_names, main_lineage_ranks, main_lineage_taxids)):
                if j == intersection_index:
                    ax.text(
                        j + 0.2, 
                        j - 0.4, 
                        f"{name} ({rank}) TaxID: {taxid}", fontsize=8, color='green', ha='left'
                    )
                    
                    y_offset = 0.6 * (intersection_indexes.count(intersection_index)) - 0.6
                    ax.text(
                        -0.2,
                        y_offset + (2 * intersection_index), 
                        taxo_string, fontsize=8, color='green', ha='right'
                    )
                    break
        else:
            y_offset = -0.6 * (intersection_indexes.count(intersection_index)) + 0.6
            ax.text(
                -0.2,
                y_offset - 0.2, 
                taxo_string, fontsize=8, color='green', ha='right'
            )
            
    ax.plot(0, 0, linestyle='-', color='blue', marker='o')
    ax.text(
        0.2, 
        -0.4, 
        main_lineage_string, 
        fontsize=8, color='blue', ha='left', fontweight='bold'
    )

    ax.set_xlim(-1, len(main_lineage_taxids) + 1)
    ax.set_ylim(-1, ylim)
    ax.axis('off')
    ax.legend([
                plt.Line2D([0], [0], color='green', marker='o', linestyle='-'),
                plt.Line2D([0], [0], color='blue', marker='o', linestyle='-')
            ], 
            ["Taxonomies found during the database search", "Queried Taxonomy"],
            loc='lower right', fontsize=8)

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    return 'phylogeny_map.png'

def get_phylogeny_intersection(lineage1, lineage2):
    for taxid in lineage1:
        if taxid in lineage2:
            return lineage2.index(taxid)
    return -1, -1  
    
def get_url(url, max_attempts=3):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = requests.get(url)
            if response.ok:
                return response
            else:
                response.raise_for_status()
        except Exception as e:
            attempts += 1
            print(f"Attempt {attempts} failed for URL: {url}. Error: {e}")
            if attempts < max_attempts:
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"Max attempts reached. Failed to fetch URL: {url}")
                raise e

    return response

def requests_get(url):
    attempt = 0
    while attempt < 3:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response
            else:
                print(f"Error: Received status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        attempt += 1
        if attempt < 3:
            print(f"Retrying in 5 seconds...")
            time.sleep(5)
    raise Exception(f"Failed to fetch data from {url} after 3 attempts")