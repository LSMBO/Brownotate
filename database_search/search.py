from .sra import *
from .genome import *
from .proteins import *

def all(scientific_name, taxonomy, illumina_only, sra_blacklist, config, no_seq=False, no_genome=False, no_prots=False, search_similar_species=False):
	synonyms_scientific_names = [scientific_name]
	if 'synonyms' in taxonomy.keys():
		synonyms_scientific_names += taxonomy['synonyms']
	dna_data = {}
	rna_data = {}
	genome_data = {}
	proteins_data = {}
	if no_prots==False:
		proteins_data = proteins(synonyms_scientific_names, taxonomy, search_similar_species)

	if no_genome==False:
		genome_data = genome(synonyms_scientific_names, taxonomy, search_similar_species)
   
	if no_seq==False:
		dna_data = getBetterSra(scientific_name, "DNA", illumina_only, sra_blacklist, config)
		rna_data = getBetterSra(scientific_name, "RNA", illumina_only, sra_blacklist, config)

	return {
		"dnaseq" : dna_data,
		"rnaseq" : rna_data,
		"genome" : genome_data,
		"proteins" : proteins_data
	}
	

def dna(scientific_name, illumina_only, sra_blacklist):
	dna = getBetterSra(scientific_name, "DNA", illumina_only=illumina_only, sra_blacklist=sra_blacklist)
	if not rna["runs"]:
		raise ValueError(f"No dna sequencing data have been found for {scientific_name} in the NCBI-SRA database.")
	return dna


def rna(scientific_name, illumina_only, sra_blacklist):
	rna = getBetterSra(scientific_name, "RNA", illumina_only=illumina_only, sra_blacklist=sra_blacklist)
	if not rna["runs"]:
		raise ValueError(f"No rna sequencing data have been found for {scientific_name} in the NCBI-SRA database.")
	return rna

def genome(synonyms_scientific_names, taxonomy, search_similar_species=False):
    return getGenomes(synonyms_scientific_names, taxonomy, search_similar_species)

def proteins(synonyms_scientific_names, taxonomy, search_similar_species=False):
    return getProteins(synonyms_scientific_names, taxonomy, search_similar_species)

