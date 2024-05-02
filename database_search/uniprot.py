import requests
import sys

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


def getTaxonID(scientific_name):
    species_parts = scientific_name.lower().split(' ')
    scientific_name_join = "%20".join(species_parts)
    url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name_join}%22)%20AND%20(rank:SPECIES)&size=500&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json()["results"]
        for result in results:
            res_scientific_name = result.get("scientificName")
            taxon_id = result.get("taxonId")
            if (scientific_name.lower() == res_scientific_name.lower()):
                return taxon_id
                

def getChildren(taxo_id, exclude_ids):
    childs = []
    url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxo_id})%20AND%20(rank:SPECIES)&size=500&format=json"
        
    # Send GET request to UniProt REST API
    response = requests.get(url)
        
    # If request is successful, parse JSON response and check if desired species/taxon ID is found
    if response.status_code == 200:
        results = response.json()["results"]       
        for result in results:
            child_taxon_id = result["taxonId"]
            if child_taxon_id not in exclude_ids:
                childs.append(child_taxon_id)

    return childs


def proteomeParse(proteome):
    proteome_id = proteome["id"]
    proteome_type = proteome["proteomeType"]
    scientific_name = proteome["taxonomy"]["scientificName"]
    taxonId = proteome["taxonomy"]["taxonId"]
    url = f"https://rest.uniprot.org/uniprotkb/search?query=(proteome:{proteome_id})&size=500&format=fasta"
    
    return {
        "database" : "uniprot",
        "data_type" : "proteins",
        "proteome_id" : proteome_id,
        "proteome_type" : proteome_type,
        "scientific_name" : scientific_name,
        "taxonId" : taxonId,
        "url" : url
    }

def getScientificNameAndRank(taxoId):
    url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{taxoId})&size=500&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        return (
            response.json()["results"][0]["scientificName"],
            response.json()["results"][0]["rank"]
        )   

def getBetterProteins(taxonomy): 
    proteome = ""
    species_id = taxonomy["taxonId"]
    url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{species_id})&size=500&format=json"
    
    # Send GET request to UniProt REST API
    response = requests.get(url)

    # If request is successful, parse JSON response and check if desired species/taxon ID is found
    if response.status_code == 200:
        results = response.json()["results"]
        for result in results:
            proteome_type = result["proteomeType"]
            if (proteome_type != "Redundant proteome" and proteome==""):
                proteome = result
            if (proteome_type == "Reference and representative proteome" or proteome_type == "Reference proteome"):
                proteome = result
        return proteomeParse(proteome)            
            
    
    # Extract taxonId from the taxonomy object
    lineage_taxo_ids = [object['taxonId'] for object in taxonomy.get("lineage")]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        # Search the children
        children =  getChildren(taxo_id, exclude_ids)
        exclude_ids.extend(children)    
        url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{taxo_id})&size=500&format=json"
    
        # Send GET request to UniProt REST API
        response = requests.get(url)
    
        # If request is successful, parse JSON response and check if desired species/taxon ID is found
        if response.status_code == 200:
            results = response.json()["results"]
            if (len(results)!=0):
                proteome = results[0]
                for result in results:
                    proteome_type = result["proteomeType"]
                    if (proteome_type == "Reference and representative proteome" or proteome_type == "Reference proteome"):
                        proteome = result

        if (proteome):
            return  proteomeParse(result)
                
    return {}        

def uniprot_fasta(url):
    file_name="output.fasta"
    r = get_url(url)
    write_fasta(r.text, file_name)
    # while there are next pages, paginate through them
    while r.links.get("next", {}).get("url"):
        r = get_url(r.links["next"]["url"])
        write_fasta(r.text, file_name)
        
def get_url(url, **kwargs):
    response = requests.get(url, **kwargs)
    if not response.ok:
        print("response not ok")
        response.raise_for_status()
        sys.exit()

    return response

def write_fasta(cnt, file_name):
    otp = open(file_name, "a")
    otp.write(cnt)
    otp.close()