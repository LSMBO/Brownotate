import requests 
import sys
import os

def taxo(species):
    # Build URL for taxon search based on whether species is a numeric taxon ID or a scientific name
    if (isinstance(species, str) and species.isnumeric()==False):
        species_parts = species.lower().split(' ')
        scientific_name = "%20".join(species_parts)
        url = f"https://rest.uniprot.org/taxonomy/search?query=(scientific:%22{scientific_name}%22)%20AND%20(rank:SPECIES)&size=500&format=json"
        
    else:
        url = f"https://rest.uniprot.org/taxonomy/search?query=(tax_id:{species})&size=500&format=json"
        species = int(species)
    
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

def downloadFasta(all_lineage, index, exclude, file_name):
    if (index>0):
        exclude.append(all_lineage[index-1]["taxonId"])
        
    target_taxonId = all_lineage[index]["taxonId"]
    
    url = f"https://rest.uniprot.org/uniprotkb/search?query=(taxonomy_id:{target_taxonId})"
    
    for ex in exclude:   
        url = url + f"%20NOT%20(taxonomy_id:{ex})"
    
    url = url + f"&size=500&format=fasta"
    
    if (os.path.exists(file_name)):
        os.remove(file_name)
        
    # Download the first page of the FASTA file
    response = get_url(url)
       
    # Write the content of the first page to file
    write_fasta(response.text, file_name)
    
    # Check if there are more pages to download
    while response.links.get("next", {}).get("url"):
        # Download the next page of the FASTA file
        response = get_url(response.links["next"]["url"])
        
        # Append the content of the next page to file
        write_fasta(response.text, file_name)
    
    # Return NOPROT if no prot
    if (not os.path.exists(file_name)):
        return "NOPROT"
    testIsEmpty = open(file_name, 'r')
    if (testIsEmpty.readlines()==[]):
        testIsEmpty.close()
        #os.remove(out)
        return "NOPROT"
    testIsEmpty.close()
        
    return file_name
        
def get_url(url, **kwargs):
    # Sends a GET request to the given URL and returns the response object.
    response = requests.get(url, **kwargs)
    
    # Check if the response is OK (status code 200)
    if not response.ok:
        response.raise_for_status()
        sys.exit()
    
    return response


def write_fasta(content, file_name):       
    # Appends the given content to the end of the file with the given name.
    with open(file_name, "a") as f:
        f.write(content)
