from .sra import *
from .genome import *
from .proteins import *

def all(scientific_name, taxonomy, illumina_only, sra_blacklist, config, no_seq=False, no_genome=False, no_prots=False):
	dna = {}
	rna = {}
	genome = {}
	proteins = {}
		
	if no_prots==False:
		proteins = getBetterProteins(scientific_name, taxonomy)
	if no_genome==False:
		genome = getBetterGenome(scientific_name, taxonomy)
	if no_seq==False:
		dna = getBetterSra(scientific_name, "DNA", illumina_only, sra_blacklist, config)
		rna = getBetterSra(scientific_name, "RNA", illumina_only, sra_blacklist, config)

	return {
		"dnaseq" : dna,
		"rnaseq" : rna,
		"genome" : genome,
		"proteins" : proteins
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

def proteins(scientific_name, taxonomy):
	proteins = getBetterProteins(scientific_name, taxonomy)
	return proteins

