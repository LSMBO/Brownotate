import argparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--species', help='Name of the species')
args = parser.parse_args()

if (isinstance(args.species, str) and args.species.isnumeric()==False):
    species_parts = args.species.lower().split(' ')
    scientific_name = "%20".join(species_parts)
    url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name}%22)%20AND%20(rank:SPECIES)&size=500&format=json"  
else:
    url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{args.species})%20AND%20(rank:SPECIES)&size=500&format=json"

response = requests.get(url)
if response.status_code == 200:
    results = response.json()["results"]
    for result in results:
        scientific_name = result["scientificName"]
        taxon_id = result["taxonId"]
        if (str(taxon_id) == args.species or scientific_name.lower() == args.species.lower()):
            print(f"{result.get('scientificName')};{result.get('taxonId')}")
            exit()
raise ValueError(f"\nTaxo \"{args.species}\" not found.")