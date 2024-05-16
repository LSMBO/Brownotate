from . import ensembl
from . import ncbi

def getGenomes(synonyms_scientific_names, taxonomy, search_similar_species):
    json_ensembl = {}
    if not isProkaryotaOrArchaea(taxonomy):
        i = 0
        while not json_ensembl and i < len(synonyms_scientific_names):
            json_ensembl = ensembl.getBetterEnsembl(synonyms_scientific_names[i], taxonomy, 'dna', False)
            i += 1
        if not json_ensembl and search_similar_species:
            json_ensembl = ensembl.getBetterEnsembl(synonyms_scientific_names[0], taxonomy, 'dna', True)
    json_refseq = {}
    i = 0
    while not json_refseq and i < len(synonyms_scientific_names):
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'refseq', 'genome', False)
        i += 1
    if not json_refseq and search_similar_species:
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'refseq', 'genome', True)
    json_genbank = {}
    i = 0  
    while not json_genbank and i < len(synonyms_scientific_names):
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'genbank', 'genome', False)
        i += 1
    if not json_genbank and search_similar_species:
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'genbank', 'genome', True)
        
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