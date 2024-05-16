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
        return proteomeParse(proteome)
    return {}

def getBetterUniprot(taxonomy, search_similar_species=False): 
    result = search_proteome(taxonomy["taxonId"])
    if search_similar_species == False or result:
        return result

    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage"))]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        children = getChildren(taxo_id, exclude_ids)
        exclude_ids.extend(children)
        
        for child_id in children:
            child_name, child_rank, childID = getScientificNameAndRank(child_id)
            if child_rank!="species":
                continue
            infos = search_proteome(childID)
            if infos:
                infos["taxonId"] = childID
                return infos
    
    if response.status_code == 200 and response.json()["results"]:
        results = response.json()["results"]
        for result in results:
            proteome_type = result["proteomeType"]
            if proteome=="":
                proteome = result
            if (proteome_type == "Reference and representative proteome" or proteome_type == "Reference proteome"):
                proteome = result                
        return proteomeParse(proteome)            
            
    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage"))]
    exclude_ids = []
    
    for taxo_id in lineage_taxo_ids:
        children =  getChildren(taxo_id, exclude_ids)
        exclude_ids.extend(children)    
        for child_id in children:
            url = f"https://rest.uniprot.org/proteomes/search?query=(organism_id:{child_id})&size=500&format=json"
            response = requests.get(url)
        
            if response.status_code == 200 and response.json()["results"]:
                results = response.json()["results"]
                if (len(results)!=0):
                    proteome = results[0]
                    for result in results:
                        proteome_type = result["proteomeType"]
                        if (proteome_type == "Reference and representative proteome" or proteome_type == "Reference proteome"):
                            proteome = result
        
            if (proteome):
                return proteomeParse(result)
                    
    return {}

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
    if response.status_code == 200 and response.json()["results"]:
        return (
            response.json()["results"][0]["scientificName"],
            response.json()["results"][0]["rank"],
            response.json()["results"][0]["taxonId"]
        )   

def getChildren(taxo_id, exclude_ids, output_type="taxonId"):
    childs = []
    url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxo_id})%20AND%20(rank:SPECIES)&size=500&format=json"
    response = get_url(url)
    results = response.json()["results"]       
    for result in results:
        child_taxon_id = result["taxonId"]
        if child_taxon_id not in exclude_ids:
            childs.append(result[output_type])
            
    # while there are next pages, paginate through them
    while response.links.get("next", {}).get("url"):
        response = get_url(response.links["next"]["url"])
        results = response.json()["results"]
        for result in results:
            child_taxon_id = result["taxonId"]
            if child_taxon_id not in exclude_ids:
                childs.append(result[output_type])

    return childs

def uniprot_fasta(url):
    file_name="output.fasta"
    r = get_url(url)
    write_fasta(r.text, file_name)
    # while there are next pages, paginate through them
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