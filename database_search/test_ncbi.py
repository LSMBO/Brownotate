import sys
sys.path.append('/home/centos/br/bin/Brownotate-1.2.0')
from ncbi import getBetterGenome, getBetterProteins

scientific_name = "Aspergillus nidulans"
taxonomy = {'scientificName': 'Emericella nidulans', 'synonyms': ['Aspergillus nidulans'], 'taxonId': 162425, 'mnemonic': 'EMEND', 'parent': {'scientificName': 'Aspergillus subgen. Nidulantes', 'taxonId': 2720870}, 'rank': 'species', 'hidden': True, 'active': True, 'otherNames': ['Aspergillus nidulellus', 'Aspergilus nidulans', 'A. nidulans', 'ATCC 10074', 'Sterigmatocystis nidulans Eidam, 1883', 'Sterigmatocystis nidulans'], 'lineage': [{'scientificName': 'cellular organisms', 'taxonId': 131567, 'rank': 'no rank', 'hidden': True}, {'scientificName': 'Eukaryota', 'commonName': 'eucaryotes', 'taxonId': 2759, 'rank': 'superkingdom', 'hidden': False}, {'scientificName': 'Opisthokonta', 'taxonId': 33154, 'rank': 'no rank', 'hidden': True}, {'scientificName': 'Fungi', 'taxonId': 4751, 'rank': 'kingdom', 'hidden': False}, {'scientificName': 'Dikarya', 'taxonId': 451864, 'rank': 'subkingdom', 'hidden': False}, {'scientificName': 'Ascomycota', 'commonName': 'ascomycetes', 'taxonId': 4890, 'rank': 'phylum', 'hidden': False}, {'scientificName': 'saccharomyceta', 'taxonId': 716545, 'rank': 'no rank', 'hidden': True}, {'scientificName': 'Pezizomycotina', 'commonName': 'filamentous ascomycetes', 'taxonId': 147538, 'rank': 'subphylum', 'hidden': False}, {'scientificName': 'leotiomyceta', 'taxonId': 716546, 'rank': 'no rank', 'hidden': True}, {'scientificName': 'Eurotiomycetes', 'taxonId': 147545, 'rank': 'class', 'hidden': False}, {'scientificName': 'Eurotiomycetidae', 'taxonId': 451871, 'rank': 'subclass', 'hidden': False}, {'scientificName': 'Eurotiales', 'commonName': 'green and blue molds', 'taxonId': 5042, 'rank': 'order', 'hidden': False}, {'scientificName': 'Aspergillaceae', 'taxonId': 1131492, 'rank': 'family', 'hidden': False}, {'scientificName': 'Aspergillus', 'taxonId': 5052, 'rank': 'genus', 'hidden': False}, {'scientificName': 'Aspergillus subgen. Nidulantes', 'taxonId': 2720870, 'rank': 'subgenus', 'hidden': False}], 'strains': [{'name': 'SRF200'}, {'name': 'FGSC 89', 'synonyms': ['FGSC A89']}, {'name': 'TDB51.1'}, {'name': 'R153'}, {'name': 'FGSC 26', 'synonyms': ['FGSC 26T']}, {'name': 'G1059'}, {'name': 'WG096'}, {'name': 'IFM 41094'}, {'name': 'GB20'}, {'name': 'IFM 46999'}, {'name': 'IFM 41395'}, {'name': 'IFM 47006'}, {'name': 'IFM 47004'}, {'name': 'JAM 2006'}, {'name': 'J283'}, {'name': 'GR5'}, {'name': 'MH 3010'}, {'name': 'A26'}, {'name': 'L20'}, {'name': 'pabaA1', 'synonyms': ['paba A1']}, {'name': 'biA1 niiA4'}, {'name': 'NRRL 322'}, {'name': 'biA1'}], 'statistics': {'reviewedProteinCount': 1045, 'unreviewedProteinCount': 10186, 'referenceProteomeCount': 0, 'proteomeCount': 0}}
bank = "refseq"

result_genome = getBetterGenome(scientific_name, taxonomy, bank)
print("Resultat pour getBetterGenome :", result_genome, '\n')

result_proteins = getBetterProteins(scientific_name, taxonomy, bank)
print("Resultat pour getBetterProteins :", result_proteins, '\n')

scientific_name = "Emericella nidulans"
result_proteins = getBetterProteins(scientific_name, taxonomy, bank)
print("Resultat pour getBetterProteins :", result_proteins, '\n')

