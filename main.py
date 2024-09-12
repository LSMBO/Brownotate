import argparse
import warnings
import logging
import os
import shutil
import uuid
import json
import datetime
import database_search
import download
import sequencing
import stats
import annotation
import pipelines

def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file '{config_file}' not found.")
    with open(config_file, 'r') as file:
        config = json.load(file)
        return config
    
def makeJson(title, object):
    with open(title, "w") as f:
        json.dump(object, f)

def copyWorkingDirectory():
    source_contents = os.listdir(os.getcwd())
    current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M")
    
    for item in source_contents:
        source_item = os.path.join(os.getcwd(), item)
        destination_item = os.path.join(STATE['output_directory'], item)
        
        if os.path.exists(destination_item):
            base_name, extension = os.path.splitext(item)
            new_item_name = f"{base_name} - Brownotate-{current_datetime}{extension}"
            destination_item = os.path.join(STATE['output_directory'], new_item_name)
            print(f"Destination item {item} already exists. Renaming to {new_item_name}")
            
        if os.path.isdir(source_item):
            shutil.copytree(source_item, destination_item)
        else:
            shutil.copy2(source_item, destination_item)
            
parser = argparse.ArgumentParser(description='Brownotate: Automatic genome annotation and protein database creation')

parser.add_argument('-s', '--species', help='Name of the species')

# Mode
parser.add_argument('--dbs-only', action='store_true', help='Compute only the database search (dbs).')
parser.add_argument('-a', '--auto', action='store_true', help='Launch Brownotate in fully automatic mode')
parser.add_argument('--no-seq', action='store_true', help='Used with dbs_only or auto if you do not want to consider the sequencing data')
parser.add_argument('--no-genome', action='store_true', help='Used with dbs_only or auto if you do not want to consider the genome data')
parser.add_argument('--no-prots', action='store_true', help='Used with dbs_only if you do not want to consider the protein data')

# Genenal
parser.add_argument('--run-id', help="Identifier of the run")
parser.add_argument('--resume', help='Identifier of the run to resume if it was interrupted')
parser.add_argument('-od', '--output-dir', default=os.getcwd(), help='Path to the output directory')
parser.add_argument("-c", "--cpus", type=int, default=int(os.cpu_count()/2), help="Number of CPUs to use")

# Assembly
parser.add_argument('-d', '--dna-sra', action='append', help='SRA accession number of the input DNA sequencing data')
parser.add_argument('-dfile', '--dna-file', action='append', help='Path to the input DNA fastq sequencing data. Separate paired files with \',\'.')
parser.add_argument('--sra-bl', action='append', help='Black listed SRA accession')
parser.add_argument('--illumina-only', action='store_true', help='Compute only the sequencing database search on Illumina datasets.')
parser.add_argument('--skip-fastp', action='store_true', help='Skip the fastp step during sequence filtering')
parser.add_argument('--skip-bowtie2', action='store_true', help='Skip the bowtie2 step that removes phix reads from the sequencing data')
parser.add_argument('--skip-filtering', action='store_true', help='Skip the two read filtering steps (skip fastp and bowtie2)')

# Annotation
parser.add_argument('-g', '--genome', help='File path to the input genome assembly')
parser.add_argument('-gu', '--genome-url', help='Assembly download URL (from Ensembl or NCBI FTP)')
parser.add_argument('-e', '--evidence', help='File path to the protein evidence database for annotation')
parser.add_argument('-eu', '--evidence-url', help='Evdence download URL (Uniprot rest url or Ensembl/NCBI FTP)')
parser.add_argument('--remove-included-sequences', action='store_true', help='Consider two protein sequences as redundant if one sequence is strictly included in the other')
parser.add_argument('--skip-remove-redundancy', action='store_true', help='Skip the step that removes redundancy in the protein sequences')

# Busco
parser.add_argument('--skip-busco-assembly', action='store_true', help='Skip the BUSCO evaluation of the assembly')
parser.add_argument('--skip-busco-annotation', action='store_true', help='Skip the BUSCO evaluation of the annotation')
parser.add_argument('--skip-busco', action='store_true', help='Skip BUSCO evaluations')

# Brownaming
parser.add_argument('--skip-brownaming', action='store_true', help='Skip the step that assigns names to each protein')
parser.add_argument('--brownaming-maxrank', help='Use by Brownaming. Rank from which the blast comparison are stopped.')
parser.add_argument('--brownaming-maxtaxo', help='Use by Brownaming. Taxo from which the blast comparison are stopped.')
parser.add_argument('--brownaming-exclude', action='append', help='Use by Brownaming. Taxo excluded from blast searches.')
parser.add_argument('--brownaming-db', action='append', help='Use by Brownaming. Custom database (fasta) to be used for blast comparisons.')

# Parse the input arguments
args = parser.parse_args()

CURRENT_DIR = os.getcwd()

# Get the directory of the script (main.py) being executed
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = load_config(os.path.join(SCRIPT_DIR, "config.json"))

#### Checks input parameters

# --resume
if args.resume:
    # Set args according to the resume run parameters
    resume_dir = os.path.join(SCRIPT_DIR, 'runs', args.resume)
    if not os.path.isdir(resume_dir):
        raise ValueError(f"\nThe resume working directory runs/{args.resume} was not found.")

    RUN_ID = args.resume
    param = {}
    with open(os.path.join(SCRIPT_DIR, 'runs', RUN_ID, "param.json"), 'r') as param_file:
        param = json.load(param_file)
    args = argparse.Namespace(**param)
    args.resume = True
    
# --species
if not args.species and not args.resume:
    raise ValueError("\nThe parameter --species is mandatory, except if you put --resume.")

# --dbs-only
if args.dbs_only:
    for arg in ['auto', 'dna_sra', 'dna_file', 'skip_fastp', 'skip_bowtie2', 'skip_filtering', 'genome', 'genome_url',
                'evidence', 'skip_busco_assembly', 'skip_busco_annotation', 'skip_busco', 'remove_included_sequences',
                'skip_remove_redundancy', 'skip_brownaming', 'brownaming_maxrank', 'brownaming_maxtaxo',
                'brownaming_exclude', 'brownaming_db']:
        if getattr(args, arg):
            raise ValueError(f"\nThe parameters --dbs-only and --{arg.replace('_', '-')} cannot be used together.")
               
# --auto
if args.auto:
    for arg in ['dna_sra', 'dna_file', 'genome', 'genome_url']:
        if getattr(args, arg):
            setattr(args, arg, None)
            warnings.warn(f"The parameter --{arg.replace('_', '-')} will be ignored because --auto is activated.", UserWarning)

# --no-seq
if args.no_seq:
    if not args.dbs_only and not args.auto:
        raise ValueError(f"\nThe parameter --no-seq cannot be used without --dbs-only or --auto.")
    if args.no_genome:
        raise ValueError(f"\nThe parameter --no-seq and --no-genome cannot be used together.")

# --no-genome
if args.no_genome:
    if not args.dbs_only and not args.auto:
        raise ValueError(f"\nThe parameter --no-genome cannot be used without --dbs-only or --auto.")

# --no-prots
if args.no_prots:
    if not args.dbs_only:
        raise ValueError(f"\nThe parameter --no-prots cannot be used without --dbs-only.")
    if args.auto:
        warnings.warn(f"The parameter --no-prots is always set to True with --auto.", UserWarning)
    
# --dna-sra and --dna-file
for arg in ['dna_sra', 'dna_file']:
    if getattr(args, arg):
        if args.sra_bl:
            raise ValueError(f"\nThe parameters --{arg} and --sra-bl cannot be used together.")
        if args.illumina_only:
            raise ValueError(f"\nThe parameters --{arg} and --illumina-only cannot be used together.")
        if args.genome:
            raise ValueError(f"\nThe parameters --{arg} and --genome cannot be used together.")
        if args.genome_url:
            raise ValueError(f"\nThe parameters --{arg} and --genome-url cannot be used together.")
# --sra-bl
if args.sra_bl:
    if args.genome:
        raise ValueError(f"\nThe parameters --sra-bl and --genome cannot be used together.")
    if args.genome_url:
        raise ValueError(f"\nThe parameters --sra-bl and --genome-url cannot be used together.")
    
# --dbs-only
if args.illumina_only:
    if args.genome:
        raise ValueError(f"\nThe parameters --illumina-only and --genome cannot be used together.")
    if args.genome_url:
        raise ValueError(f"\nThe parameters --illumina-only and --genome-url cannot be used together.")
    
# --genome
if args.genome:
    for arg in ['skip_fastp', 'skip_bowtie2', 'skip_filtering', 'genome_url']:
        if getattr(args, arg):
            raise ValueError(f"\nThe parameters --genome and --{arg.replace('_', '-')} cannot be used together.")
        
# --genome-url
if args.genome_url:
    for arg in ['skip_fastp', 'skip_bowtie2', 'skip_filtering', 'genome']:
        if getattr(args, arg):
            raise ValueError(f"\nThe parameters --genome_url and --{arg.replace('_', '-')} cannot be used together.")

# --evidence
if args.evidence and args.evidence_url:
    raise ValueError(f"\nThe parameters --evidence and --evidence-url cannot be used together.")
    
# --skip-remove-redundancy
if args.skip_remove_redundancy and args.remove_included_sequences:
    raise ValueError(f"\nThe parameters --skip-remove-redundancy and --remove-included-sequences cannot be used together.")

# --skip-brownaming
if args.skip_brownaming:
    for arg in ['brownaming_maxtaxo', 'brownaming_exclude', 'brownaming_db']:
        if getattr(args, arg):
            warnings.warn(f"The parameters --{arg.replace('_', '-')} will be ignored because you put --skip-brownaming.", UserWarning)

# --brownaming-db
if args.brownaming_db:
    for arg in ['brownaming_maxrank', 'brownaming_maxtaxo', 'brownaming_exclude']:
        if getattr(args, arg):
            raise ValueError(f"\nThe parameters --brownaming-db and --{arg.replace('_', '-')} cannot be used together.")

# cpus
if args.cpus > os.cpu_count():
    raise ValueError(f"\nError: You have provided {args.cpus} CPUs, but your machine has only {os.cpu_count()} CPUs available.")

### Variable assignment

# Checks if the path of the input files exists
input_dnaseq_files = []
if args.dna_file:
    for f in args.dna_file:
        files = f.split(',')
        abs_files = []
        for file in files:
            if not os.path.exists(file):
                raise FileNotFoundError(f'File {file} not found')
            abs_files.append(os.path.abspath(file))
        input_dnaseq_files.append(
            {"file_name": abs_files,
             "platform" : "unknown"}
            )

input_genome_file = ""  
if args.genome:
    if not os.path.exists(args.genome):
        raise FileNotFoundError(f'File {f} not found')
    input_genome_file = os.path.abspath(args.genome)

input_evidence_file = ""
if args.evidence:
    print(args.evidence)
    if not os.path.exists(args.evidence):
        raise FileNotFoundError(f'File {f} not found')
    input_evidence_file = os.path.abspath(args.evidence)


# Check Brownaming parameters
BROWNAMING_MAX_RANK = ""
if args.brownaming_maxrank:
    possible_rank = ["forma", "varietas", "subspecies", "species", "species subgroup", "species group", "subgenus", "genus", "subtribe", "tribe", "subfamily", "family", "superfamily", "parvorder", "infraorder", "suborder", "order", "superorder", "subcohort", "cohort", "infraclass", "subclass", "class", "superclass", "subphylum", "phylum", "superphylum", "subkingdom", "kingdom", "superkingdom"]
    if args.brownaming_maxrank.lower() in possible_rank:
        BROWNAMING_MAX_RANK = args.brownaming_maxrank.lower()

BROWNAMING_MAX_TAXO = ""
if args.brownaming_maxtaxo:
    taxo = database_search.UniprotTaxo(args.brownaming_maxtaxo)
    if (taxo is None):
        raise ValueError(f"\nTaxo \"{taxo}\" not found.")
    else:
        BROWNAMING_MAX_TAXO = taxo.get_tax_id()

BROWNAMING_EXCLUDE = []
if args.brownaming_exclude:
    for taxo in args.brownaming_exclude:
        taxo = database_search.UniprotTaxo(taxo)
        if (taxo is None):
            raise ValueError(f"\nTaxo \"{taxo}\" not found.")
        else:
            BROWNAMING_EXCLUDE.append(taxo.get_tax_id())

BROWNAMING_CUSTOM_DB = []
if args.brownaming_db:
    for file in args.brownaming_db:
        if not os.path.exists(file):
            raise FileNotFoundError(f'File {file} not found')
        else:
            BROWNAMING_CUSTOM_DB.append(os.path.abspath(file))      

# 0 : Does not remove anu sequence
# 1 : Removes identical sequences
# 2 : Removes sequences already included in another sequence
REDUNDANCY_MODE = 1
if args.skip_remove_redundancy:
    REDUNDANCY_MODE = 0
if (args.remove_included_sequences):
    REDUNDANCY_MODE = 2

OUTPUT_DIRECTORY = os.path.abspath(args.output_dir)
if not os.path.isdir(OUTPUT_DIRECTORY):
    parent_dir = os.path.dirname(args.output_dir)
    if os.path.isdir(parent_dir):
        os.makedirs(OUTPUT_DIRECTORY)
    else:
        raise FileNotFoundError(f"{OUTPUT_DIRECTORY} is not a valid directory")

# Create taxo.json with taxonomy data
taxo_uniprot = {}
try:
    taxo_uniprot = database_search.UniprotTaxo(args.species)
except ValueError as e:
    raise ValueError(f"\nTaxonomy data not found: {e}")
TAXON_ID = taxo_uniprot.get_tax_id()
SCIENTIFIC_NAME = taxo_uniprot.get_scientific_name()
  
if args.resume:    
    WORKING_DIR = os.path.join(SCRIPT_DIR, "runs", RUN_ID)
    os.chdir(WORKING_DIR)
    STATE = {}
    with open("state.json", 'r') as state_file:
        STATE = json.load(state_file)

else:
    if args.run_id:
        RUN_ID = args.run_id
    else:
        RUN_ID = str(uuid.uuid4())

    # Create a directory with the name of the run ID 
    WORKING_DIR = os.path.join(SCRIPT_DIR, "runs", RUN_ID)
    os.mkdir(WORKING_DIR)
    os.chdir(WORKING_DIR)
    
    # Add the parameters in this working directory in param.json
    makeJson("param.json", vars(args))
    makeJson(f"taxo.json", taxo_uniprot.get_taxonomy())   


# Path of the output directory
OUTPUT_FASTA_FILENAME = f"{SCIENTIFIC_NAME.replace(' ', '_')}_Brownotate.fasta"
OUTPUT_FASTA_FILEPATH = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FASTA_FILENAME)

# Create a logger object
logger = logging.getLogger('main_logger')
logger.setLevel(logging.INFO)

# Create a file manager
log_path = 'main.log'
file_handler = logging.FileHandler(log_path)
file_handler.setLevel(logging.INFO)

# Create a formatter with the desired format
formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%d/%m/%Y - %H:%M')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


if args.resume:
    with open(log_path,"a") as log_file:
        log_file.write('\n')
    logger.info(f'Brownotate is resume')
else:
    # Initiates STATE
    STATE = {
        "scientific_name" : SCIENTIFIC_NAME,
        "taxo" : taxo_uniprot.get_taxonomy(),
        "output_fasta_filepath" : OUTPUT_FASTA_FILEPATH,
        "output_directory" : OUTPUT_DIRECTORY,
        "config" : CONFIG,
        "run_id" : RUN_ID,
        "args" : vars(args),
        "brownaming": {
            "max_rank" : BROWNAMING_MAX_RANK,
            "max_taxo" : BROWNAMING_MAX_TAXO,
            "exclude" : BROWNAMING_EXCLUDE,
            "custom_db" : BROWNAMING_CUSTOM_DB
        }
    }
    makeJson(f"state.json", STATE)
    
    logger.info(f'Brownotate start')

if args.dbs_only:
    pipelines.run_database_search(STATE, database_search, logger, dbs_only=True, no_seq=args.no_seq, no_genome=args.no_genome, no_prots=args.no_prots, search_similar_species=True)

if args.auto:
    
    # 1. Search data --> Database_Search.json
    if not os.path.exists('Database_Search.json'):
        data = pipelines.run_database_search(STATE, database_search, logger, no_seq=args.no_seq, no_genome=args.no_genome, no_prots=True, search_similar_species=False)
    else:
        with open('Database_Search.json', 'r') as file:    
            data = json.load(file)
    
    # 2. Select the better data --> Better_data.json
    if not os.path.exists('Better_data.json'):
        better_data = pipelines.run_better_data(data, database_search, logger)
        if better_data["data_type"] == "dnaseq":
            STATE["dnaseq_entries"] = better_data
        else:
            STATE["genome_entry"] = better_data    
    else:
        with open('Better_data.json', 'r') as file:
            better_data = json.load(file)
    makeJson("state.json", STATE)
    
    # 3. Download the better data
    if better_data["data_type"] == "dnaseq":
        if "dnaseq_files" not in STATE:
            logger.info(f"Download the sequencing datasets ...")
            downloaded_dnaseq_files = pipelines.run_download(better_data, download)
            STATE["dnaseq_files"] = downloaded_dnaseq_files
            logger.info(f"The sequencing datasets have been successfully downloaded.")
        # Skip this step for the resumed run
        else:
            logger.info(f"The sequencing have already been downloaded.")
    
    elif better_data["data_type"] == "genome":
        if "genome_file" not in STATE:
            logger.info(f"Download the genome file ...")
            genome_entry = pipelines.run_download(better_data, download)
            STATE["genome_entry"] = genome_entry
            STATE["genome_file"] = genome_entry["file_name"]
            logger.info(f"The genome file have been successfully downloaded.")        
    makeJson("state.json", STATE)
    
# If the user provides custom inputs
else:
    
    # If necessary, search and download the sequencing datasets
    if args.dna_sra:
        
        # Search the inputed accessions in the SRA database
        if "dnaseq_entries" not in STATE:
            sra_entries = pipelines.run_get_sra_entries(STATE, database_search)
            STATE["dnaseq_entries"] = sra_entries
            logger.info(f"The sequencing datasets that you have requested have been found in the NCBI-SRA database.")
        # Skip this step for the resumed run
        else:
            sra_entries = STATE["dnaseq_entries"]
            logger.info(f"The sequencing datasets have already been found in the last run.")
        makeJson("state.json", STATE)
        
        # Download the sequencing datasets
        if "dnaseq_files" not in STATE:
            logger.info(f"Download the sequencing datasets ...")
            downloaded_dnaseq_files = pipelines.run_download(STATE["dnaseq_entries"], download)
            STATE["dnaseq_files"] = downloaded_dnaseq_files 
            logger.info(f"The sequencing datasets have been successfully downloaded.")
        # Skip this step for the resumed run
        else:
            logger.info(f"The sequencing have already been downloaded.")
        makeJson("state.json", STATE)

    # If sequencing files have been provided 
    if args.dna_file:
        STATE["dnaseq_files"] = input_dnaseq_files

    # If the genome download url has been provided
    if args.genome_url:
        genome_file = pipelines.run_download(args.genome_url, download) 
        STATE['genome_file'] = genome_file['file_name']
    # If the genome file has been provided 
    if args.genome:
        STATE["genome_file"] = input_genome_file
        
    makeJson("state.json", STATE)

# Filter the sequencing data
if "dnaseq_files" in STATE:
    if not args.skip_fastp and not args.skip_filtering:
        
        # Remove low quality reads
        logger.info(f"Filter the low quality sequencing reads with fastp.")
        if "fastp_files" not in STATE:
            logger.info(f"Run fastp...")
            STATE["fastp_files"] = pipelines.run_fastp(STATE, sequencing)
            makeJson("state.json", STATE)
            logger.info(f"Fastp successfully completed.")
        
        # Skip this step for the resumed run
        else:
            logger.info("Fastp process has already been computed.")

    if not args.skip_bowtie2 and not args.skip_filtering:
        
        # Remove phix reads
        logger.info(f"Filter the sequencing reads bellowing to the phix genome using bowtie2.")
        if "phix_files" not in STATE:
            logger.info(f"Run bowtie2...")
            STATE["phix_files"] = pipelines.run_bowtie2(STATE, sequencing)
            makeJson("state.json", STATE)
            logger.info(f"Bowtie2 successfully completed.")
            
        # Skip this step for the resumed run
        else:
            logger.info(f"Bowtie2 process has already been completed.")

    # Compute the assembly
    logger.info(f"Assemble you DNA sequencing data into a genome using Megahit.")
    if "genome_file" in STATE:
        logger.info(f"The genome has already been assembled.")
    else:
        logger.info(f"Run Megahit for the assembly...")
        STATE["genome_file"] = pipelines.run_megahit(STATE, sequencing)
        makeJson("state.json", STATE)
        logger.info(f"The genome has been successfully assembled.")    

# Busco completeness evaluation
if not args.skip_busco_assembly and not args.skip_busco:
    logger.info(f"Evaluate the completeness of the genome using Busco.")
    if os.path.exists("Busco_genome.json"):
        logger.info(f"The evaluation has already been completed.")
    else:
        pipelines.run_busco(STATE, stats, mode="genome")
        logger.info(f"The busco evaluation has successfully been computed.")

# Annotation with augustus for eukaryots and with prokka for prokaryots
annotation_tool = "augustus"
for entry in taxo_uniprot.get_taxonomy()["lineage"]:
    if entry["taxonId"] == 2 or entry["taxonId"] == 2157:
        annotation_tool = "prokka"
        break
    
if annotation_tool=="prokka":
    logger.info(f"{SCIENTIFIC_NAME} is a bacteria or an archaea, the Prokka pipeline will be used.")
    if "annotation" in STATE:
        logger.info(f"Prokka annotation has already been computed.")
    else:
        logger.info(f"Run Prokka...")
        STATE["annotation"] = pipelines.run_prokka(STATE, annotation)
        makeJson("state.json", STATE)
        logger.info(f"Prokka annotation has been successfully completed.")    
        
if annotation_tool=="augustus":
    logger.info(f"{SCIENTIFIC_NAME} is an eukaryote species, the Augustus pipeline will be used.")
    # Searching for evidence file for augustus annotation 
    
    # If the evidence download url has been provided
    if args.evidence_url:
        STATE["evidence_file"] = pipelines.run_download(args.evidence_url, download)
    
    # If the evidence file have been provided
    if args.evidence: 
        STATE["evidence_file"] = input_evidence_file
    
    else: # The evidence file have to be searched and downloaded
        if "evidence_search" in STATE:
            logger.info(f"The evidence data has already been found.")
        else:
            logger.info(f"Search for the different evidence annotations...")
            STATE["evidence_search"] = pipelines.run_get_evidence(STATE, database_search)

        if "evidence_file" in STATE:
            logger.info(f"The evidence file has already been downloaded.")
        else:           
            logger.info(f"Download the evidence file...")
            STATE["evidence_file"] = pipelines.run_download(STATE["evidence_search"], download)["file_name"]
            
             
    makeJson("state.json", STATE)
    logger.info(f"The best evidence annotation have been successfully downloaded.")
    
    # Split the genome
    logger.info(f"Split the genome.")   
    if "subgenomes" in STATE:
        logger.info(f"The genome has already been splited.")
    else:
        STATE["subgenomes"] = pipelines.run_split_genome(STATE, annotation)
        logger.info(f"Genome successfully splited.") 
    makeJson("state.json", STATE)

    # Scipio
    logger.info(f"Searching for genes using scipio with the evidence proteins.")   
    if "genesraw" in STATE:
        logger.info(f"Scipio has already been completed.")
    else:
        STATE["genesraw"] = pipelines.run_scipio(STATE, annotation, flex=False)
        logger.info(f"Scipio has been successfully completed.")
    makeJson("state.json", STATE)

    # Create Gene prediction model
    logger.info(f"Build a gene prediction model.")   
    if "num_genes" in STATE:
        logger.info(f"The gene prediction model has already been initiated.")
    else:
        STATE["num_genes"] = pipelines.run_model(STATE, annotation)
        logger.info(f"The gene prediction model has been initiated.")  
    makeJson("state.json", STATE)
    
    # If necessary, rerun scipio with more flexible parameters. Genesraw --> Genesraw_v2
    if STATE["num_genes"] < 400:
        logger.info(f"The gene prediction model cannot be trained because scipio did not found enough genes (<400). It rerun scipio with more flexible parameters.")    
        if "genesraw_v2" in STATE:
            logger.info(f"Flexible scipio have already been computed.")
        else:
            if os.path.exists(STATE["genesraw"]):
                os.remove(STATE["genesraw"])
            STATE["genesraw_v2"] = pipelines.run_scipio(STATE, annotation, flex=True) 
        
        STATE["genesraw"] = STATE["genesraw_v2"]
        makeJson("state.json", STATE)
        logger.info(f"Flexible scipio have been successfully completed.")      
        
        logger.info(f"Retrain the gene prediction model with the new genes identified with the flexible scipio.")
        if "num_genes_v2" in STATE:
            num_genes = STATE["num_genes_v2"]
            logger.info(f"This step has already be computed in the last run.")
        else:
            num_genes = pipelines.run_model(STATE, annotation)
            STATE["num_genes_v2"] = num_genes
            makeJson("state.json", STATE)
            logger.info(f"The gene prediction model has been successfully retrained.")
        if num_genes < 400:
            print(f"Error : Number of genes and rawgenes is too low in the run {OUTPUT_DIRECTORY}, the annotation cannot continue. Please try with a better genome or with better protein evidences.")
            logger.info(f"Even with flexible scipio, the gene prediction model cannot be trained with such a low number of genes. Brownotate is interruped.")
            copyWorkingDirectory()
            exit()
    
    # Optimizes the model    
    logger.info(f"Optimizing the gene prediction model.")
    if "optimize_model" in STATE:
        logger.info(f"Gene prediction model optimization has already been computed.")
    else:
        logger.info(f"Run the gene prediction model optimization with optimize_augustus.")
        STATE["optimize_model"] = pipelines.run_optimize_augustus(STATE, annotation)
        makeJson("state.json", STATE)
        logger.info(f"Gene prediction model optimization has been successfully computed.")      

    
    logger.info(f"Annotating the genome by searching for protein coding gene using the gene prediction model.")    
    if "annotation" in STATE:  
        logger.info(f"Augustus annotation has already been computed.")
    else:
        logger.info(f"Run Augustus.")
        STATE["annotation"] = pipelines.run_augustus(STATE, annotation)
        makeJson("state.json", STATE)
        logger.info(f"Augustus annotation has been successfully completed.")
       
if REDUNDANCY_MODE != 0:
    logger.info(f"Remove the redundancy.")  
    if "annotation_red" in STATE:  
        logger.info(f"Redundancy has already been eliminated.")
    else:
        STATE["annotation_red"] = pipelines.run_remove_redundancy(REDUNDANCY_MODE, STATE, annotation) #annotation.remove_redundancy(ANNOTATION, REDUNDANCY_MODE)
        makeJson("state.json", STATE)
        logger.info(f"Redundancy has been successfully eliminated.")
    
if not args.skip_brownaming:
    logger.info(f"Annotate the predicted proteins using Brownaming (assigns a name).")
    if "annotation_brownaming" in STATE:
        logger.info(f"Brownaming annotation has already been realized.")
    else:
        STATE["annotation_brownaming"] = pipelines.run_brownaming(STATE, annotation)
        makeJson("state.json", STATE)
        logger.info(f"Brownaming annotation has been successfully computed.")

# Busco completeness evaluation
if not args.skip_busco_annotation and not args.skip_busco:
    logger.info(f"Evaluate the completeness of the annotation using Busco.")
    if os.path.exists("Busco_annotation.json"):
        logger.info(f"The evaluation has already been completed.")
    else:
        pipelines.run_busco(STATE, stats, mode='proteins')
        logger.info(f"The busco evaluation has successfully been computed.")


# Cleaning working directory
if "all_completed" in STATE:
    print(f"Brownotate was already completed. Your protein annotation is available in {OUTPUT_DIRECTORY}. Thank you for using Brownotate")
    logger.info(f"Brownotate was already completed. Your protein annotation is available in {OUTPUT_DIRECTORY}. Thank you for using Brownotate")
else:
    STATE["all_completed"] = "completed"
    makeJson("state.json", STATE)
    print(f"Brownotate is completed. Your protein annotation is available in {OUTPUT_DIRECTORY}. Thank you for using Brownotate")
    logger.info(f"Brownotate is completed. Your protein annotation is available in {OUTPUT_DIRECTORY}. Thank you for using Brownotate")

    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)   

    copyWorkingDirectory()
    if os.path.exists(OUTPUT_FASTA_FILEPATH):
        os.chdir("..")
        shutil.rmtree(RUN_ID)

