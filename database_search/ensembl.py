from . import ensembl_ftp
from . import uniprot
from . import ncbi

def getBetterEnsembl(scientific_name, taxonomy, data_type, search_similar_species=False):
    result = ensembl_ftp.getDataFromFTP(data_type, [scientific_name])  # Pass a list of scientific names
    if search_similar_species == False or result:
        return result
    
    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage"))]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        children_names = uniprot.getChildren(taxo_id, exclude_ids, "scientificName")
        infos = ensembl_ftp.getDataFromFTP(data_type, children_names)
        if infos:
            taxonId = uniprot.getTaxonID(infos["scientific_name"])
            if not taxonId:
                taxonId = ncbi.getTaxonID(infos["scientific_name"])
            infos["taxonId"] = taxonId
            return infos
