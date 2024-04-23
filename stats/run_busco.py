import requests
import argparse
import os
import json
import busco


def taxo(species):
    # Build URL for taxon search based on whether species is a numeric taxon ID or a scientific name
    if (isinstance(species, str) and species.isnumeric()==False):
        species_parts = species.lower().split(' ')
        scientific_name = "%20".join(species_parts)
        url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name}%22)%20AND%20(rank:SPECIES)&size=500&format=json"
        
    else:
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{species})%20AND%20(rank:SPECIES)&size=500&format=json"
    
    # Send GET request to UniProt REST API
    response = requests.get(url)
    
    # If request is successful, parse JSON response and check if desired species/taxon ID is found
    if response.status_code == 200:
        results = response.json()["results"]
        for result in results:
            scientific_name = result["scientificName"]
            taxon_id = result["taxonId"]
            if (taxon_id == species or scientific_name.lower() == species.lower()):
                return result 
    return None

parser = argparse.ArgumentParser(description='Run Busco')

parser.add_argument('-i', '--input', help='Name of the input fasta file')
parser.add_argument('-t', '--taxo', help='Name of the species')
parser.add_argument('-m', '--mode', choices=['genome', 'proteins'], help='Busco mode (genome or proteins)')
parser.add_argument('-lp', '--lineage-path', help='Directory path containing the eukaryota_odb10/prokaryota_odb10/archaea_odb10 directories')
parser.add_argument("-c", "--cpus", type=int, default=12, help="Number of CPUs to use")

args = parser.parse_args()

if not args.input:
    raise ValueError("Error: You did not set the -i/--input argument")
if not args.taxo:
    raise ValueError("Error: You did not set the -t/--taxo argument")
if not args.mode:
    raise ValueError("Error: You did not set the -m/--mode argument")

if not os.path.exists(args.input):
    raise FileNotFoundError(f'File {args.input} not found')
INPUT_FASTA = args.input

TAXO = taxo(args.taxo)
if TAXO is None:
    raise ValueError(f"Taxo \"{args.taxo}\" not found.")
TAXON_ID = TAXO.get("taxonId")
SCIENTIFIC_NAME = TAXO.get("scientificName").replace(' ','_')
   
MODE = args.mode

LINEAGE_PATH = os.path.dirname(os.path.abspath(__file__))

output_json_name = f"Busco_species={SCIENTIFIC_NAME}_mode={MODE}.json" 

result = busco.busco(input_file=INPUT_FASTA, taxo=TAXO, mode=MODE, cpus=args.cpus, busco_lineage_dirpath=LINEAGE_PATH, custom=True)
with open(output_json_name, "w") as f:
    json.dump(result, f)