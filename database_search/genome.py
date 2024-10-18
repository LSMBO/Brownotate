from . import ensembl as dbs_ensembl
from ftp import ensembl as ftp_ensembl
from . import ncbi

def getGenomes(synonyms_scientific_names, taxonomy, search_similar_species, proteins_data, config):
    # ENSEMBL
    json_ensembl = {}
    if not isProkaryotaOrArchaea(taxonomy):
        if proteins_data and 'ensembl' in proteins_data and 'url' in proteins_data['ensembl'] and proteins_data['ensembl']['scientific_name'] in synonyms_scientific_names:
            json_ensembl = ftp_ensembl.getAssemblyFTPrepository(proteins_data['ensembl']['url'], proteins_data['ensembl']['scientific_name']) 
        i = 0
        while not json_ensembl and i < len(synonyms_scientific_names):
            json_ensembl = dbs_ensembl.getBetterEnsembl(synonyms_scientific_names[i], taxonomy, 'dna', False, config)
            i += 1
        if not json_ensembl and search_similar_species:
            json_ensembl = dbs_ensembl.getBetterEnsembl(synonyms_scientific_names[0], taxonomy, 'dna', True, config)
    
    # REFSEQ
    json_refseq = {}
    json_genbank = {}
    if proteins_data and 'refseq' in proteins_data and 'url' in proteins_data['refseq'] and proteins_data['refseq']['scientific_name'] in synonyms_scientific_names:
        json_refseq = ncbi.fetchAssemblyDetails(proteins_data['refseq']['entrez_id'], 'genome', 'refseq')
    i = 0
    while not json_refseq and i < len(synonyms_scientific_names):
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'refseq', 'genome', False, config)
        i += 1
    if json_refseq and json_refseq['scientific_name'] in synonyms_scientific_names:
        json_genbank = ncbi.fetchAssemblyDetails(json_refseq['entrez_id'], 'genome', 'genbank')
    if not json_refseq and search_similar_species:
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'refseq', 'genome', True, config)
    
    # GENBANK
    if proteins_data and 'genbank' in proteins_data and 'url' in proteins_data['genbank'] and proteins_data['genbank']['scientific_name'] in synonyms_scientific_names:
        json_genbank = ncbi.fetchAssemblyDetails(proteins_data['genbank']['entrez_id'], 'genome', 'genbank')
    i = 0  
    while not json_genbank and i < len(synonyms_scientific_names):
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'genbank', 'genome', False, config)
        i += 1
    if not json_genbank and search_similar_species:
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'genbank', 'genome', True, config)
        
    return {
        "ensembl": json_ensembl,
        "refseq": json_refseq,
        "genbank": json_genbank
    }

def isProkaryotaOrArchaea(taxonomy):
    lineage = taxonomy["lineage"]
    for taxo in lineage:
        if (taxo["scientificName"] == "Bacteria" or taxo["scientificName"] == "Archaea"):
            return True
    return False