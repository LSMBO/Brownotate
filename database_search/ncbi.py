import subprocess
import os
import json
from utils import load_config
from flask_app.commands import run_command

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']


def fetch_taxon_id(scientific_name, run_id):
    command = f"datasets summary taxonomy taxon \"{scientific_name}\""
    stdout, stderr, returncode = run_command(command, run_id, env=env)
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'ncbi datasets command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
        }), 500 
    if stdout.startswith('{'):
        results = json.loads(stdout).get("reports", [])
        if results:
            return results[0]['taxonomy']['tax_id']
    return None

def fetch_taxonomy_data(taxid, run_id):
    command = f"datasets summary taxonomy taxon {taxid}"

    stdout, stderr, returncode = run_command(command, run_id, env=env)
    if returncode != 0:          
        return jsonify({
            'status': 'error',
            'message': f'ncbi datasets command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
        }), 500 
    if stdout.startswith('{'):
        result = json.loads(stdout).get("reports", [])
        if result:
            if results[0]['taxonomy']['tax_id'] == int(taxid):
                taxonomy_data = results[0]['taxonomy']
                taxonomy_data['taxonId'] = taxonomy_data.pop('tax_id')
                classification = taxonomy_data['classification']
                lineage = []
                for rank in reversed(list(classification.keys())):
                    taxo = classification[rank]
                    lineage.append({
                        "rank": rank,
                        "scientificName": taxo["name"],
                        "taxonId": taxo["id"]
                    })
                taxonomy_data['lineage'] = lineage
                return taxonomy_data
    return None
        

def fetch_ncbi_genomes(taxid, assembly_source, assembly_level, annotated, limit, run_id):
    command = f"datasets summary genome taxon {taxid} --assembly-source {assembly_source} --assembly-level {assembly_level}"
    if annotated:
        command += " --annotated"
    command += f" --limit {limit}"
    
    stdout, stderr, returncode = run_command(command, run_id, env=env)
    if returncode != 0:
        return jsonify({
            'status': 'error',
            'message': f'ncbi datasets command failed',
            'command': command,
            'stderr': stderr,
            'stdout': stdout,
        }), 500    
    if stdout.startswith('{'):
        results = json.loads(stdout).get("reports", [])
        return results
    return []


def set_genome_data(genome, is_annotated, assembly_source):
    accession = genome["accession"]
    genome_data = {
        "database": "NCBI",
        "accession": accession,
        "scientific_name": genome["organism"]["organism_name"],
        "taxid": genome["organism"]["tax_id"],
        'url': f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/"
    }
    
    download_command = ["datasets", "download", "genome", "accession", accession]
    
    if is_annotated:
        genome_data["data_type"] = f"ncbi_{assembly_source}_proteins"
        download_command += ["--filename", f"{accession}_annotation.zip", "--include", "protein"]
        if "busco" in genome["annotation_info"]:
            busco = round(100 * (genome["annotation_info"]["busco"]["complete"] + genome["annotation_info"]["busco"]["duplicated"]))
            genome_data['busco'] = f"{busco}%"
        else:
            genome_data['busco'] = None
            
    else:
        download_command += ["--filename", f"{accession}_assembly.zip", "--include", "genome"]
        genome_data["assembly_level"] = genome["assembly_info"]["assembly_level"]
        genome_data["assembly_length"] = genome['assembly_stats']['total_sequence_length']
        genome_data["data_type"] = f"ncbi_{assembly_source}_genome"
    
    genome_data["download_command"] = download_command
    return genome_data


def get_ncbi_genomes(data, assembly_source, run_id, limit=999):
    annotated_genomes = []
    genomes = []
    output_annotated_genomes = []
    output_genomes = []
    for taxo in data['taxonomy']['lineage']:
        # First search for annotated genomes, if a genome is annotated, it will also have an assembled DNA version
        for level in ["chromosome", "complete", "scaffold", "contig"]:
            if len(annotated_genomes) >= limit:
                break
            results = fetch_ncbi_genomes(taxo['taxonId'], assembly_source, level, True, limit-len(genomes), run_id)
            annotated_genomes += results
            genomes += results
        
        if len(genomes) < limit:
            # If we don't have enough genomes, search for unannotated genomes
            for level in ["chromosome", "complete", "scaffold", "contig"]:
                if len(genomes) >= limit:
                    break
                results = fetch_ncbi_genomes(taxo['taxonId'], assembly_source, level, False, limit, run_id)
                for result in results:
                    if result not in genomes:
                        genomes.append(result)
        
        if annotated_genomes and not output_annotated_genomes:
            for annotated_genome in annotated_genomes:
                annotated_genome_data = set_genome_data(annotated_genome, True, assembly_source)
                output_annotated_genomes.append(annotated_genome_data)

        if genomes and not output_genomes:
            for genome in genomes:
                genome_data = set_genome_data(genome, False, assembly_source)
                output_genomes.append(genome_data)
        
        if output_annotated_genomes and output_genomes:
            return output_annotated_genomes, output_genomes
        
    return output_annotated_genomes, output_genomes

