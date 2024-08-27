from . import ensembl_ftp
from database_search.uniprot import UniprotTaxo
from . import ncbi

def getBetterEnsembl(scientific_name, taxonomy, data_type, search_similar_species=False):
    results = ensembl_ftp.getDataFromFTP(data_type, [scientific_name])
    if results:
        taxonId = ncbi.getTaxonID(results["scientific_name"])
        results["taxonId"] = taxonId
        return results
    if search_similar_species == False:
        return results
    
    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage"))]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        children_names = UniprotTaxo.fetch_children(taxo_id, exclude_ids, "scientificName")
        results = ensembl_ftp.getDataFromFTP(data_type, children_names)
        if results:
            taxonId = UniprotTaxo.fetch_taxon_id(results["scientific_name"])
            if not taxonId:
                taxonId = ncbi.getTaxonID(results["scientific_name"])
            results["taxonId"] = taxonId
            return results
    return {}
