from . import uniprot
from . import ensembl
from . import ncbi

def getProteins(synonyms_scientific_names, taxonomy, search_similar_species):
    json_ensembl = {}
    if not isProkaryotaOrArchaea(taxonomy):
        i = 0
        while not json_ensembl and i < len(synonyms_scientific_names):
            json_ensembl = ensembl.getBetterEnsembl(synonyms_scientific_names[i], taxonomy, 'pep', False)
            i += 1
        if not json_ensembl and search_similar_species:
            json_ensembl = ensembl.getBetterEnsembl(synonyms_scientific_names[0], taxonomy, 'pep', True)
    
    json_uniprot = {}
    i = 0
    while not json_uniprot and i < len(synonyms_scientific_names):
        json_uniprot = uniprot.getBetterUniprot(taxonomy, False)
        i += 1
    if not json_uniprot and search_similar_species:
        json_uniprot = uniprot.getBetterUniprot(taxonomy, True)
    
    json_refseq = {}
    i = 0
    while not json_refseq and i < len(synonyms_scientific_names):
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'refseq', 'proteins', False)
        i += 1
    if not json_refseq and search_similar_species:
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'refseq', 'proteins', True)

    json_genbank = {}
    i = 0  
    while not json_genbank and i < len(synonyms_scientific_names):
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'genbank', 'proteins', False)
        i += 1
    if not json_genbank and search_similar_species:
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'genbank', 'proteins', True)
        
    return {
        "ensembl": json_ensembl,
        "uniprot": json_uniprot,
        "refseq": json_refseq,
        "genbank": json_genbank
    }

def isProkaryotaOrArchaea(taxonomy):
    lineage = taxonomy["lineage"]
    for taxo in lineage:
        if (taxo["scientificName"] == "Bacteria" or taxo["scientificName"] == "Archaea"):
            return True
    return False