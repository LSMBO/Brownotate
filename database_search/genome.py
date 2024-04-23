from . import ensembl
from . import ncbi


def getBetterGenome(scientific_name, taxonomy):
    if not isProkaryotaOrArchaea(taxonomy):
        json_ensembl = ensembl.getBetterGenome(scientific_name)
    else:
        json_ensembl = {}
    json_refseq = ncbi.getBetterGenome(scientific_name, taxonomy, "refseq")
    json_genbank = ncbi.getBetterGenome(scientific_name, taxonomy, "genbank")
    # Création de l'objet JSON contenant les informations de génome
    genome_info = {
        "ensembl": json_ensembl,
        "refseq": json_refseq,
        "genbank": json_genbank
    }

    # Retourne l'objet JSON
    return genome_info

def isProkaryotaOrArchaea(taxonomy):
    lineage = taxonomy["lineage"]
    for taxo in lineage:
        if (taxo["scientificName"] == "Bacteria" or taxo["scientificName"] == "Archaea"):
            return True
    return False