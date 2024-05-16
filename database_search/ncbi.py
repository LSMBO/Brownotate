from . import ncbi_ftp
from . import uniprot
import requests

def getTaxonID(scientific_name):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "taxonomy",
        "term": scientific_name,
        "retmode": "json"
    }
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        taxon_ids = data.get("esearchresult", {}).get("idlist", [])
        if taxon_ids:
            return taxon_ids[0]

    return None


def getBetterNCBI(scientific_name, taxonomy, bank, data_type, search_similar_species=False): # data_type = genome or proteins
    lineage_scientific_names = [object['scientificName'] for object in taxonomy.get("lineage")]
    categories = getNCBICategories(lineage_scientific_names)
    result = ncbi_ftp.getDataFromFTP(data_type, scientific_name, categories, bank)
    if search_similar_species == False or "url" in result:
        if "url" in result:
            result["taxonId"] = getTaxonID(result["scientific_name"])  
        return result
    
    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage"))]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        children =  uniprot.getChildren(taxo_id, exclude_ids)
        exclude_ids.extend(children)
        
        for child_id in children:
            child_name, child_rank, child_id = uniprot.getScientificNameAndRank(child_id)
            if child_rank!="species":
                continue
            result = ncbi_ftp.getDataFromFTP(data_type, child_name, categories, bank)
            if result:
                result["taxonId"] = child_id
                return result  
    
def getNCBICategories(lineage_scientific_names): 
    categories=[]
       
    if ("Mammalia" in lineage_scientific_names):
        categories = ["vertebrate_mammalian"]
    elif ("Bacteria" in lineage_scientific_names):
        categories = ["bacteria"]
    elif ("Fungi" in lineage_scientific_names):
        categories = ["fungi"]
    elif ("Archaea" in lineage_scientific_names):
        categories = ["archaea"]
    elif ("Vertebrata" in lineage_scientific_names and "Mammalia" not in lineage_scientific_names):
        categories = ["vertebrate_other"]
    elif ("Viridiplantae" in lineage_scientific_names):
        categories = ["plant"]
    elif ("Viruses" in lineage_scientific_names):
        categories = ["viral"]
    elif ("Vertebrata" not in lineage_scientific_names):
        categories = ["invertebrate", "protozoa"]

    return categories


