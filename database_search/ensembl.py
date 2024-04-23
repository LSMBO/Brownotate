from . import ensembl_ftp
from . import uniprot

def getBetterGenome(scientific_name):
    result = ensembl_ftp.getDataFromFTP("dna", scientific_name)
    taxonId = uniprot.getTaxonID(result["scientific_name"])
    result["taxonId"] = taxonId  
    return result


def getBetterEvidence(scientific_name, taxonomy):
    mySpecies = ensembl_ftp.getDataFromFTP("pep", scientific_name)
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
                infos = ensembl_ftp.getDataFromFTP("pep", child_name)
                if infos["url"]:
                    taxonId = uniprot.getTaxonID(infos["scientific_name"])
                    infos["taxonId"] = taxonId    
                    return infos