import json, os, datetime
import ftplib
import time
import sys
from flask import Blueprint, request, jsonify
from flask_app.database import insert_one
from timer import timer

dbs_ensembl_bp = Blueprint('dbs_ensembl_bp', __name__)
ensembl_ftp_species = json.load(open('database_search/ensembl_ftp_species.json'))


@dbs_ensembl_bp.route('/dbs_ensembl', methods=['POST'])
def dbs_ensembl():
    try:
        start_time = timer.start()
        user = request.json.get('user')
        taxonomy = request.json.get('taxonomy')
        options = request.json.get('options', {})
        current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
        
        if not user or not taxonomy:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        ensembl_genomes, ensembl_annotated_genomes = get_ensembl(taxonomy)
        timer_str = timer.stop(start_time)
        
        mongo_query = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': {
                'ensembl_genomes': ensembl_genomes,
                'ensembl_annotated_genomes': ensembl_annotated_genomes
            }
        }
        insert_one('ensembl', mongo_query)

        response_data = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'options': options,
            'data': {
                'ensembl_genomes': ensembl_genomes,
                'ensembl_annotated_genomes': ensembl_annotated_genomes
            }
        }
        
        return jsonify({'status': 'success', 'data': response_data}), 200
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': 'An unexpected error occurred',
            'timer': timer.stop(start_time), 
            'details': str(e)
        }), 500


def get_ensembl(taxonomy):
    assembly_list = []
    proteins_list = []
    if is_excluded_taxonomy(taxonomy):
        return assembly_list, proteins_list
    for taxo in taxonomy['lineage']:
        taxid = str(taxo['taxonId'])
        if taxid in ensembl_ftp_species:
            ensembl_scientific_names = ensembl_ftp_species[taxid]['scientific_names']
            ensembl_taxids = ensembl_ftp_species[taxid]['taxids']
            for i, ensembl_scientific_name in enumerate(ensembl_scientific_names):
                assembly, proteins = get_data_from_ftp(ensembl_scientific_name, ensembl_taxids[i])
                assembly_list.append(assembly)
                proteins_list.append(proteins)
            if assembly_list and proteins_list:
                return assembly_list, proteins_list
    return [], []

def is_excluded_taxonomy(taxonomy):
    excluded_groups = {"Bacteria", "Archaea", "Viridiplantae"}
    for taxo in taxonomy['lineage']:
        if taxo['scientificName'] in excluded_groups:
            return True
    return False


def get_data_from_ftp(scientific_name, taxid):
	ftp = connect_ftp("ftp.ensembl.org")
	url = f"pub/current_fasta/{scientific_name}"
		
	cwd_ftp(ftp, f"{url}/dna/")
	files = ftp.nlst()
	for file in files:
		if file.endswith("dna.toplevel.fa.gz"):
			assembly_url = f"ftp.ensembl.org/{url}/dna/{file}"
		elif file.endswith("dna.primary_assembly.fa.gz"):
			assembly_url = f"ftp.ensembl.org/{url}/dna/{file}"

	cwd_ftp(ftp, f"../pep/")
	files = ftp.nlst()
	for file in files:
		if file.endswith(".pep.all.fa.gz"):
			proteins_url = f"ftp.ensembl.org/{url}/pep/{file}"
			accession = file.split(".pep.all")[0]

	assembly_level = "toplevel"
	if "primary_assembly" in assembly_url:
		assembly_level = "primary assembly"
	elif "chromosome" in assembly_url:
		assembly_level = "chromosome"
	assembly = {
		"accession": accession,
		"url": f"https://ftp.ensembl.org/{url}/dna/",
		"download_url": assembly_url,
		"data_type": "genome",
		"assembly_level": assembly_level,
		"ftp": "ftp.ensembl.org",
		"database": "ENSEMBL",
		"scientific_name": scientific_name.capitalize().replace("_", " "),
  		"taxid": taxid
	}
 
	proteins = {
		"accession": accession,
		"url": f"https://ftp.ensembl.org/{url}/pep/",
		"download_url": proteins_url,
		"data_type": "proteins",
		"ftp": "ftp.ensembl.org",
		"database": "ENSEMBL",
		"scientific_name": scientific_name.capitalize().replace("_", " "),
		"taxid": taxid
	}
	ftp.quit()
	return assembly, proteins


def connect_ftp(ftp_name, retries=5, wait_seconds=10):
    attempt = 0
    connected = False
    ftp = None
    while attempt < retries and not connected:
        try:
            ftp = ftplib.FTP(ftp_name)
            ftp.login()
            connected = True
        except ftplib.all_errors as e:
            attempt += 1
            print(f"Failed to connect to {ftp_name}. Attempt {attempt}/{retries}.")
            print(f"Error message: {str(e)}")
            if attempt < retries:
                print(f"Waiting {wait_seconds} seconds before trying again...")
                time.sleep(wait_seconds)
    if not connected:
        print(f"Failed to connect to {ftp_name} after {retries} attempts. Exiting.")
        sys.exit(1)

    return ftp

def cwd_ftp(ftp, dir, testing=False, retries=5, wait_seconds=10):
    if testing:
        try:
            ftp.cwd(dir)
            return True
        except ftplib.all_errors as e:
            return False
    else:
        attempt = 0
        success = False
        while attempt < retries and not success:
            try:
                ftp.cwd(dir)
                success = True
            except ftplib.all_errors as e:
                attempt += 1
                print(f"Failed to connect to {dir}. Attempt {attempt}/{retries}.")
                print(f"Error message: {str(e)}")
                if attempt < retries:
                    print(f"Waiting {wait_seconds} seconds before trying again...")
                    time.sleep(wait_seconds)
        if not success:
            print(f"Failed to connect to {dir} after {retries} attempts. Exiting.")
            sys.exit(1)

