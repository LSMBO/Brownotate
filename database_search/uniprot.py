import requests
import sys

class UniprotTaxo:
    def __init__(self, species, fast_mode=False):
        if isinstance(species, str) and not species.isnumeric():
            self.scientific_name = species
            self.taxID = self.fetch_taxon_id(species)
        else:
            self.scientific_name = self.fetch_scientific_name_and_rank(species)[0]
            self.taxID = species

        if not fast_mode:
            self.taxonomy = self.fetch_taxonomy_data()
            if not self.taxonomy:
                raise ValueError(f"Taxonomy data for \"{species}\" not found.")
            self.proteome = self.fetch_proteome_data()
            self.swissprot = self.fetch_swissprot_data()
            self.trembl = self.fetch_trembl_data()
        else:
            self.taxonomy = None
            self.proteome = self.fetch_proteome_data()
            self.swissprot = None
            self.trembl = None

    @staticmethod
    def fetch_taxon_id(scientific_name):
        species_parts = scientific_name.lower().split(' ')
        scientific_name_join = "%20".join(species_parts)
        url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name_join}%22)%20AND%20(rank:SPECIES)&size=500&format=json"
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json()["results"]
            for result in results:
                res_scientific_name = result.get("scientificName")
                taxon_id = result.get("taxonId")
                if scientific_name.lower() == res_scientific_name.lower():
                    return taxon_id
        return None
    
    @staticmethod
    def fetch_scientific_name_and_rank(taxoId):
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{taxoId})&size=500&format=json"
        response = requests.get(url)
        if response.status_code == 200 and response.json()["results"]:
            return (
                response.json()["results"][0]["scientificName"],
                response.json()["results"][0]["rank"],
                response.json()["results"][0]["taxonId"]
            )
        return (None, None)

    def fetch_taxonomy_data(self):
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{self.taxID})%20AND%20(rank:SPECIES)&size=500&format=json"
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json()["results"]
            for result in results:
                taxon_id = result["taxonId"]
                if taxon_id == int(self.taxID):
                    return result 
        return None
    
    def fetch_proteome_data(self):
        url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{self.taxID})&size=500&format=json"
        response = requests.get(url)
        if response.status_code == 200 and response.json()["results"]:
            results = response.json()["results"]
            proteome = ""
            for result in results:
                proteome_type = result["proteomeType"]
                if proteome_type != "Redundant proteome" and proteome == "":
                    proteome = result
                if proteome_type == "Reference and representative proteome" or proteome_type == "Reference proteome":
                    proteome = result
            return {
                "database": "uniprot",
                "data_type": "proteins",
                "proteome_id": proteome["id"],
                "proteome_type": proteome["proteomeType"],
                "scientific_name": proteome["taxonomy"]["scientificName"],
                "taxonId": proteome["taxonomy"]["taxonId"],
                "url": f"https://rest.uniprot.org/uniprotkb/search?query=(proteome:{proteome['id']})&size=500&format=fasta"
            }
        return {}

    def fetch_swissprot_data(self):
        url = f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxID})%20AND%20(reviewed:true)&format=json"
        response = requests.get(url)
        if response.status_code == 200 and response.json()["results"]:
            results = response.json()["results"]
            if results:
                return {
                    "database": "swissprot",
                    "data_type": "proteins",
                    "scientific_name": results[0].get("organism", {}).get("scientificName"),
                    "taxonId": results[0].get("organism", {}).get("taxonId"),
                    "sequence_count": int(self.taxonomy["statistics"]["reviewedProteinCount"]),
                    "url": f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxID})%20AND%20(reviewed:true)&format=fasta"
                }
        return {}

    def fetch_trembl_data(self):
        url = f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxID})%20AND%20(reviewed:false)&format=json"
        response = requests.get(url)
        if response.status_code == 200 and response.json()["results"]:
            results = response.json()["results"]
            if results:
                return {
                    "database": "trembl",
                    "data_type": "proteins",
                    "scientific_name": results[0].get("organism", {}).get("scientificName"),
                    "taxonId": results[0].get("organism", {}).get("taxonId"),
                    "sequence_count": int(self.taxonomy["statistics"]["unreviewedProteinCount"]),
                    "url": f"https://rest.uniprot.org/uniprotkb/search?query=(organism_id:{self.taxID})%20AND%20(reviewed:false)&format=fasta"
                }
        return {}

    def fetch_related_proteome(self):
        lineage_taxo_ids = [object['taxonId'] for object in reversed(self.taxonomy.get("lineage"))]
        exclude_ids = []
        for taxo_id in lineage_taxo_ids:
            children = self.fetch_children(taxo_id, exclude_ids)
            exclude_ids.extend(children)
            for child_id in children:
                child_name, child_rank, childID = self.fetch_scientific_name_and_rank(child_id)
                if child_rank!="species":
                    continue
                uniprot_taxo = UniprotTaxo(childID, fast_mode=True)
                proteome = uniprot_taxo.get_proteome()
                if proteome:
                    return proteome
        return {}
    
    @staticmethod
    def fetch_children(taxo_id, exclude_ids, output_type="taxonId"):
        childs = []
        url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxo_id})%20AND%20(rank:SPECIES)&size=500&format=json"
        response = get_url(url)
        results = response.json()["results"]       
        for result in results:
            child_taxon_id = result["taxonId"]
            if child_taxon_id not in exclude_ids:
                childs.append(result[output_type]) 
        while response.links.get("next", {}).get("url"):
            response = get_url(response.links["next"]["url"])
            results = response.json()["results"]
            for result in results:
                child_taxon_id = result["taxonId"]
                if child_taxon_id not in exclude_ids:
                    childs.append(result[output_type])
        return childs

    def get_tax_id(self):
        return self.taxID

    def get_scientific_name(self):
        return self.scientific_name

    def get_taxonomy(self):
        return self.taxonomy

    def get_proteome(self):
        return self.proteome
    
    def get_swissprot(self):
        return self.swissprot

    def get_trembl(self):
        return self.trembl
    
def search_proteome(taxID):
    url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{taxID})&size=500&format=json"
    response = requests.get(url)
    if response.status_code == 200 and response.json()["results"]:
        results = response.json()["results"]
        proteome = ""
        for result in results:
            proteome_type = result["proteomeType"]
            if (proteome_type != "Redundant proteome" and proteome==""):
                proteome = result
            if (proteome_type == "Reference and representative proteome" or proteome_type == "Reference proteome"):
                proteome = result
        return {
            "database" : "uniprot",
            "data_type" : "proteins",
            "proteome_id" : proteome["id"],
            "proteome_type" : proteome["proteomeType"],
            "scientific_name" : proteome["taxonomy"]["scientificName"],
            "taxonId" : proteome["taxonomy"]["taxonId"],
            "url" : f"https://rest.uniprot.org/uniprotkb/search?query=(proteome:{proteome['id']})&size=500&format=fasta"
        }
    return {}



def uniprot_fasta(url):
    file_name="output_testing.fasta"
    r = get_url(url)
    write_fasta(r.text, file_name)
    print(r.links)
    while r.links.get("next", {}).get("url"):
        r = get_url(r.links["next"]["url"])
        write_fasta(r.text, file_name)
        
def get_url(url):
    response = requests.get(url)
    if not response.ok:
        response.raise_for_status()
        sys.exit()

    return response

def write_fasta(cnt, file_name):
    otp = open(file_name, "a")
    otp.write(cnt)
    otp.close()
    