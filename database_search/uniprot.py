import requests
import sys
import time
import database_search.ncbi as ncbi

class UniprotTaxo:
    def __init__(self, taxid, run_id, reference_taxid=None):
        try:
            self.taxid = int(taxid)
        except ValueError:
            self.taxid = self.fetch_taxon_id(taxid, run_id)
            if self.taxid is None:
                print(f"Error: Invalid taxon ID or scientific name '{taxid}'.", file=sys.stderr)
                raise ValueError(f"Invalid taxon ID or scientific name '{taxid}'.")
        self.reference_taxid = reference_taxid
        self.taxonomy = self.fetch_taxonomy_data(reference_taxid)
        if self.taxonomy is None:
            self.taxonomy = ncbi.fetch_taxonomy_data(taxid, run_id)

    def fetch_taxon_id(self, scientific_name, run_id):
        species_parts = scientific_name.lower().split(' ')
        scientific_name_join = "%20".join(species_parts)
        url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name_join}%22)&size=500&format=json"
        response = get_url(url)
        if response:
            results = response.json()["results"]
            for result in results:
                res_scientific_name = result.get("scientificName")
                taxon_id = result.get("taxonId")
                if scientific_name.lower() == res_scientific_name.lower():
                    return taxon_id
        taxon_id = ncbi.fetch_taxon_id(scientific_name, run_id)
        if taxon_id:
            return taxon_id
        return None
    
    def fetch_scientific_name_and_rank(taxoId):
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{taxoId})&size=500&format=json"
        response = get_url(url)
        if response and response.json()["results"]:
            return (
                response.json()["results"][0]["scientificName"],
                response.json()["results"][0]["rank"],
                response.json()["results"][0]["taxonId"]
            )
        return (None, None)

    def fetch_taxonomy_data(self, reference_id=None):
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{self.taxid})&size=500&format=json"
        response = get_url(url)
        if response:
            results = response.json()["results"]
            for result in results:
                taxon_id = result["taxonId"]
                if taxon_id == int(self.taxid):
                    lineage = []
                    is_bacteria = False
                    for i in range(len(result['lineage']) - 1, -1, -1):
                        lineage.append(result['lineage'][i])
                        if result['lineage'][i]['scientificName'] == "Bacteria":
                            is_bacteria = True
                    lineage = [{'scientificName': result['scientificName'], 
                                'taxonId': result['taxonId'], 
                                'rank': result['rank']}] + [
                                elt for elt in reversed(result['lineage']) 
                                if not elt['hidden'] or 
                                (elt['hidden'] and reference_id and elt['taxonId'] == reference_id)
                              ]
                    result['lineage'] = lineage
                    result['is_bacteria'] = is_bacteria
                    return result
        return None
    
    def search_swissprot_data(self):
        url = f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxid})%20AND%20(reviewed:true)&format=json"
        response = get_url(url)
        if response and response.json()["results"]:
            results = response.json()["results"]
            if results:
                return {
                    "database": "UniprotKB",
                    "data_type": "swissprot",
                    "scientific_name": results[0].get("organism", {}).get("scientificName"),
                    "taxonId": results[0].get("organism", {}).get("taxonId"),
                    "sequence_count": int(self.taxonomy["statistics"]["reviewedProteinCount"]),
                    "url": f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxid})%20AND%20(reviewed:true)&format=fasta"
                }
        return {}

    def search_trembl_data(self):
        url = f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxid})%20AND%20(reviewed:false)&format=json"
        response = get_url(url)
        if response and response.json()["results"]:
            results = response.json()["results"]
            if results:
                return {
                    "database": "UniprotKB",
                    "data_type": "trembl",
                    "scientific_name": results[0].get("organism", {}).get("scientificName"),
                    "taxonId": results[0].get("organism", {}).get("taxonId"),
                    "sequence_count": int(self.taxonomy["statistics"]["unreviewedProteinCount"]),
                    "url": f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxid})%20AND%20(reviewed:false)&format=fasta"
                }
        return {}
   
    def get_taxid(self):
        return self.taxid

    def get_scientific_name(self):
        return self.taxonomy['scientificName']

    def get_taxonomy(self):
        return self.taxonomy

    def get_proteome(self):
        return self.proteome
    
    def get_swissprot(self):
        return self.swissprot

    def get_trembl(self):
        return self.trembl

    @staticmethod
    def search_proteome(taxid, limit=3):
        url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{taxid})&size=500&format=json"
        response = get_url(url)
        proteomes = []
        if response and response.json()["results"]:
            results = response.json()["results"]
            proteome_count = 0
            for result in results:
                if proteome_count == limit:
                    return proteomes
                proteome_type = result["proteomeType"]
                proteomes.append({
                    "database": "UniprotKB",
                    "data_type": "uniprot_proteome",
                    "accession": result["id"],
                    "proteome_type": proteome_type,
                    "scientific_name": result["taxonomy"]["scientificName"],
                    "taxid": result["taxonomy"]["taxonId"],
                    "download_url": f"https://rest.uniprot.org/uniprotkb/stream?query=proteome:{result['id']}&format=fasta",
                    "url": f"https://www.uniprot.org/proteomes/{result['id']}"
                })
                proteome_count += 1
        return proteomes

    @staticmethod
    def get_children_with_proteome(taxid, max_childs, exclude_ids=[]):
        childs = []
        url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxid})%20AND%20(rank:SPECIES%20OR%20rank:STRAIN%20OR%20rank:SUBSPECIES)&size=500&format=json"
        response = get_url(url)
        results = response.json()["results"]       
        for result in results:
            child_taxon_id = result['taxonId']
            proteome_count = result['statistics']['proteomeCount']
            if proteome_count > 0 and child_taxon_id not in exclude_ids:
                childs.append((result['taxonId'], result['scientificName']))
            if len(childs) >= max_childs:
                return childs
        while response.links.get("next", {}).get("url"):
            response = get_url(response.links["next"]["url"])
            results = response.json()["results"]
            for result in results:
                child_taxon_id = result["taxonId"]
                proteome_count = result['statistics']['proteomeCount']
                if proteome_count > 0 and child_taxon_id not in exclude_ids:
                    childs.append((result['taxonId'], result['scientificName']))
                if len(childs) >= max_childs:
                    return childs
        return childs

    @staticmethod
    def get_children(taxid, exclude_ids=[]):
        childs = []
        url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxid})%20AND%20(rank:SPECIES%20OR%20rank:STRAIN%20OR%20rank:SUBSPECIES)&size=500&format=json"
        response = get_url(url)
        results = response.json()["results"]       
        for result in results:
            child_taxon_id = result['taxonId']
            if child_taxon_id not in exclude_ids:
                childs.append((result['taxonId'], result['scientificName']))

        while response.links.get("next", {}).get("url"):
            response = get_url(response.links["next"]["url"])
            results = response.json()["results"]
            for result in results:
                child_taxon_id = result["taxonId"]
                if child_taxon_id not in exclude_ids:
                    childs.append((result['taxonId'], result['scientificName']))
        return childs

def uniprot_fasta(url):
    file_name="output_testing.fasta"
    r = get_url(url)
    write_fasta(r.text, file_name)
    print(r.links)
    while r.links.get("next", {}).get("url"):
        r = get_url(r.links["next"]["url"])
        write_fasta(r.text, file_name)
        
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

def write_fasta(cnt, file_name):
    otp = open(file_name, "a")
    otp.write(cnt)
    otp.close()
    