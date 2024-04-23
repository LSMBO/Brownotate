from .sra import *
from .genome import *
from .evidence import *

def all(scientific_name, taxonomy, illumina_only, sra_blacklist, config, no_seq=False, no_genome=False):
	
	if no_seq:
		genome = getBetterGenome(scientific_name, taxonomy)
		result = {
			"genome" : genome
		}

	elif no_genome:
		dna = getBetterSra(scientific_name, "DNA", illumina_only, sra_blacklist, config)
		rna = getBetterSra(scientific_name, "RNA", illumina_only, sra_blacklist, config)   
		result = {
		"dnaseq" : dna,
		"rnaseq" : rna,
		}  
	else:
		dna = getBetterSra(scientific_name, "DNA", illumina_only, sra_blacklist, config)
		rna = getBetterSra(scientific_name, "RNA", illumina_only, sra_blacklist, config)
		genome = getBetterGenome(scientific_name, taxonomy)
		result = {
		"dnaseq" : dna,
		"rnaseq" : rna,
		"genome" : genome
		}
	return result

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

def evidence(scientific_name, taxonomy):
    evidence = getBetterEvidence(scientific_name, taxonomy)
    return evidence

