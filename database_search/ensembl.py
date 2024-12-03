from ftp import ensembl
from database_search.uniprot import UniprotTaxo
from . import ncbi

def getBetterEnsembl(scientific_name, taxonomy, data_type, search_similar_species=False, config=None):
    results = ensembl.getDataFromFTP(data_type, [scientific_name])
    if results:
        taxonId = ncbi.getTaxonID(results["scientific_name"], config)
        results["taxonId"] = taxonId
        return results
    if search_similar_species == False:
        return results
    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage"))]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        if taxo_id == 6656:
            if data_type == 'pep':
                return {
                    'url': '/pub/release-112/fasta/drosophila_melanogaster/pep/Drosophila_melanogaster.BDGP6.46.pep.all.fa.gz', 
                    'data_type': 'proteins', 
                    'quality': '', 
                    'ftp': 'ftp.ensembl.org', 
                    'database': 'ensembl', 
                    'scientific_name': 'Drosophila melanogaster',
                    'taxoId': 7227
                }
            else:
                return {
                    'url': '/pub/release-112/fasta/drosophila_melanogaster/dna/Drosophila_melanogaster.BDGP6.46.dna.toplevel.fa.gz', 
                    'data_type': 'genome', 
                    'quality': 'toplevel', 
                    'ftp': 'ftp.ensembl.org', 
                    'database': 'ensembl', 
                    'scientific_name': 'Drosophila melanogaster'
                }
        children_names = UniprotTaxo.fetch_children(taxo_id, exclude_ids, "scientificName")
        results = ensembl.getDataFromFTP(data_type, children_names)
        if results:
            taxonId = UniprotTaxo.fetch_taxon_id(results["scientific_name"])
            if not taxonId:
                taxonId = ncbi.getTaxonID(results["scientific_name"], config)
            results["taxonId"] = taxonId
            return results
    return {}
