from database_search.uniprot import UniprotTaxo
from . import ensembl
from . import ncbi
import time

def displayTime(elapsed_time):
    minutes, seconds = divmod(elapsed_time, 60)
    seconds, milliseconds = divmod(seconds, 1)
    return f"{int(minutes)}:{int(seconds):02}:{int(milliseconds * 1000):03}"


def getProteins(synonyms_scientific_names, taxonomy, search_similar_species):
    start_time = time.time()
    json_ensembl = {}
    if not isProkaryotaOrArchaea(taxonomy):
        i = 0
        while not json_ensembl and i < len(synonyms_scientific_names):
            json_ensembl = ensembl.getBetterEnsembl(synonyms_scientific_names[i], taxonomy, 'pep', False)
            i += 1
        if not json_ensembl and search_similar_species:
            json_ensembl = ensembl.getBetterEnsembl(synonyms_scientific_names[0], taxonomy, 'pep', True)
        print(f"Ensembl proteins search completed ! A protein dataset has been found for {json_ensembl['scientific_name']}. Elapsed time : {displayTime(time.time() - start_time)}")
    
    start_time = time.time()
    json_uniprot_ok = False
    i = 0
    while not json_uniprot_ok and i < len(synonyms_scientific_names):
        uniprot_taxo = UniprotTaxo(synonyms_scientific_names[i])
        json_uniprot_proteome = uniprot_taxo.get_proteome()
        json_uniprot_swissprot = uniprot_taxo.get_swissprot()
        json_uniprot_trembl = uniprot_taxo.get_trembl()
        if json_uniprot_proteome or json_uniprot_swissprot or json_uniprot_trembl:
            json_uniprot_ok = True
        i += 1
    if not json_uniprot_proteome and search_similar_species:
        uniprot_taxo = UniprotTaxo(synonyms_scientific_names[0])
        json_uniprot_proteome = uniprot_taxo.fetch_related_proteome()
    print(f"Uniprot proteome search completed ! A protein dataset has been found for {json_uniprot_proteome['scientific_name']}. Elapsed time : {displayTime(time.time() - start_time)}")	
    json_refseq = {}
    start_time = time.time()
    i = 0
    while not json_refseq and i < len(synonyms_scientific_names):
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'refseq', 'proteins', False)
        i += 1
    if not json_refseq and search_similar_species:
        json_refseq = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'refseq', 'proteins', True)
    print(f"RefSeq proteins search completed ! A protein dataset has been found for {json_refseq['scientific_name']}. Elapsed time : {displayTime(time.time() - start_time)}")	
    json_genbank = {}
    start_time = time.time()
    i = 0  
    while not json_genbank and i < len(synonyms_scientific_names):
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[i], taxonomy, 'genbank', 'proteins', False)
        i += 1
    if not json_genbank and search_similar_species:
        json_genbank = ncbi.getBetterNCBI(synonyms_scientific_names[0], taxonomy, 'genbank', 'proteins', True)
    print(f"Genbank proteins search completed ! A protein dataset has been found for {json_genbank['scientific_name']}. Elapsed time : {displayTime(time.time() - start_time)}")
    return {
        "ensembl": json_ensembl,
        "uniprot_proteome": json_uniprot_proteome,
        "uniprot_swissprot": json_uniprot_swissprot,
        "uniprot_trembl": json_uniprot_trembl,
        "refseq": json_refseq,
        "genbank": json_genbank
    }

def isProkaryotaOrArchaea(taxonomy):
    lineage = taxonomy["lineage"]
    for taxo in lineage:
        if (taxo["scientificName"] == "Bacteria" or taxo["scientificName"] == "Archaea"):
            return True
    return False