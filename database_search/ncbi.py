from . import ncbi_ftp
from . import uniprot

def getBetterGenome(scientific_name, taxonomy, bank):
    lineage_scientific_names = [object['scientificName'] for object in taxonomy.get("lineage")]
    categories = getNCBICategories(lineage_scientific_names)
    result = ncbi_ftp.getDataFromFTP("genome", scientific_name, categories, bank)
    taxonId = uniprot.getTaxonID(result["scientific_name"])
    result["taxonId"] = taxonId  
    return result


def getBetterEvidence(scientific_name, taxonomy, bank):
    lineage_scientific_names = [object['scientificName'] for object in taxonomy.get("lineage")]
    categories = getNCBICategories(lineage_scientific_names)
    mySpecies = ncbi_ftp.getDataFromFTP("proteins", scientific_name, categories, bank)
    if mySpecies["url"]:
        taxonId = uniprot.getTaxonID(mySpecies["scientific_name"])
        mySpecies["taxonId"] = taxonId  
        return mySpecies
    else:
        lineage_taxo_ids = [object['taxonId'] for object in taxonomy.get("lineage")]
        exclude_ids = [taxonomy.get("taxonId")]
        for taxo_id in lineage_taxo_ids:
            children = uniprot.getChildren(taxo_id, exclude_ids)
            exclude_ids.extend(children)
            for child_id in children:
                child_name, child_rank = uniprot.getScientificNameAndRank(child_id)
                if child_rank!="species":
                    continue
                infos = ncbi_ftp.getDataFromFTP("proteins", child_name, categories, bank)
                if infos["url"]:
                    taxonId = uniprot.getTaxonID(infos["scientific_name"])
                    infos["taxonId"] = taxonId
                    return infos    

    
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
