from . import uniprot
from . import ensembl
from . import ncbi

def getBetterProteins(scientific_name, taxonomy):
    if not isProkaryotaOrArchaea(taxonomy):
        json_ensembl = ensembl.getBetterProteins(scientific_name, taxonomy)
    else:
        json_ensembl = {}
    
    json_uniprot = uniprot.getBetterProteins(taxonomy)
    json_refseq = ncbi.getBetterProteins(scientific_name, taxonomy, "refseq")
    json_genbank = ncbi.getBetterProteins(scientific_name, taxonomy, "genbank")
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