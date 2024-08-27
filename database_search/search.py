from .sra import *
from .genome import *
from .proteins import *
import time

def displayTime(elapsed_time):
	minutes, seconds = divmod(elapsed_time, 60)
	seconds, milliseconds = divmod(seconds, 1)
	return f"{int(minutes)}:{int(seconds):02}:{int(milliseconds * 1000):03}"


def all(scientific_name, taxonomy, illumina_only, sra_blacklist, config, no_seq=False, no_genome=False, no_prots=False, search_similar_species=False):
	synonyms_scientific_names = [scientific_name]
	if 'synonyms' in taxonomy.keys():
		synonyms_scientific_names += taxonomy['synonyms']
	json_dnaseq = {}
	json_rnaseq = {}
	genome_data = {}
	proteins_data = {}
	if no_prots==False:
		start_time = time.time()
		proteins_data = proteins(synonyms_scientific_names, taxonomy, search_similar_species)
		print(f"Proteins search completed ! elapsed time : {displayTime(time.time() - start_time)}")		

	if no_genome==False:
		start_time = time.time()
		genome_data = genome(synonyms_scientific_names, taxonomy, search_similar_species)
		print(f"Assembly search completed ! elapsed time : {displayTime(time.time() - start_time)}")	
  
	if no_seq==False:
		# DNAseq
		start_time = time.time()
		json_dnaseq = getBetterSra(synonyms_scientific_names, taxonomy, "DNA", illumina_only, sra_blacklist, config, search_similar_species=False)
		if not json_dnaseq and search_similar_species:
			json_dnaseq = getBetterSra(synonyms_scientific_names, taxonomy, "DNA", illumina_only, sra_blacklist, config, search_similar_species=True)
		print(f"DNAseq search completed ! elapsed time : {displayTime(time.time() - start_time)}")		

		# RNAseq
		#start_time = time.time()
		#json_rnaseq = getBetterSra(synonyms_scientific_names, taxonomy, "RNA", illumina_only, sra_blacklist, config, search_similar_species=False)
		#if not json_rnaseq and search_similar_species:
		#	start_time = time.time()
		#	json_rnaseq = getBetterSra(synonyms_scientific_names, taxonomy, "RNA", illumina_only, sra_blacklist, config, search_similar_species=True)
		#print(f"RNAseq search completed ! elapsed time : {displayTime(time.time() - start_time)}")

	return {
		"dnaseq" : json_dnaseq,
		"rnaseq" : json_rnaseq,
		"genome" : genome_data,
		"proteins" : proteins_data
	}
	
def genome(synonyms_scientific_names, taxonomy, search_similar_species=False):
	return getGenomes(synonyms_scientific_names, taxonomy, search_similar_species)

def proteins(synonyms_scientific_names, taxonomy, search_similar_species=False):
	return getProteins(synonyms_scientific_names, taxonomy, search_similar_species)



# def dna(scientific_name, taxonomy, illumina_only, sra_blacklist):
# 	dna = getBetterSra(scientific_name, taxonomy, "DNA", illumina_only=illumina_only, sra_blacklist=sra_blacklist)
# 	if not rna["runs"]:
# 		raise ValueError(f"No dna sequencing data have been found for {scientific_name} in the NCBI-SRA database.")
# 	return dna


# def rna(scientific_name, taxonomy, illumina_only, sra_blacklist):
# 	rna = getBetterSra(scientific_name, taxonomy, "RNA", illumina_only=illumina_only, sra_blacklist=sra_blacklist)
# 	if not rna["runs"]:
# 		raise ValueError(f"No rna sequencing data have been found for {scientific_name} in the NCBI-SRA database.")
# 	return rna

