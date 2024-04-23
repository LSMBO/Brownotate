import argparse
import json
import logging
import os
import shutil
import uuid
import warnings
import uniprot
import blast
import concentric

def makeJson(title, object):
    with open(title, "w") as f:
        json.dump(object, f)
        
# Define the argparse parser and add all the possible input arguments
parser = argparse.ArgumentParser(description='Brownaming: Propagating Sequence Names for Similar Organisms')

# Required argument
parser.add_argument('-p', '--proteins', help='Protein fasta file')
parser.add_argument('-s', '--species', help='Name of the species or taxonId')

# Optional arguments
parser.add_argument('-mr', '--max-rank', help='maxrank (included)')
parser.add_argument('-mt', '--max-taxo', help='maxtaxonId (included')
parser.add_argument('-e', '--exclude', action='append', help='taxonID exclude from the research')
parser.add_argument('--short', action='store_true', help='Adapts BLAST parameters for particularly short sequences')
parser.add_argument('-db', '--database', action='append', help='Database path')
parser.add_argument('--resume', help='Id of the run to resume if it was interrupted')
parser.add_argument('-dir', '--output-dir', help='Path to the output directory')
parser.add_argument("-o", "--output-file", help="Name of the fasta output file (Just the filename, not the path)")
parser.add_argument("-c", "--cpus", type=int, default=12, help="Number of CPUs to use")

# Parse the input arguments
args = parser.parse_args()

# Get the directory of the script being executed
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Check input parameters (if the run is not a resume)
if not args.resume:
    if not args.proteins:
        raise ValueError("-p/--proteins parameter is mandatory (except if you use --resume)")
    if not args.species:
        raise ValueError("-s/--species parameter is mandatory (except if you use --resume)")
    
    # Checks if the path of the input files exists
    if not os.path.exists(args.proteins):
        raise FileNotFoundError(f'File {args.proteins} not found')
    PROTEINS = os.path.abspath(args.proteins)
    args.proteins = PROTEINS
            
    CUSTOM_DB = []
    if args.database:
        for file in args.database:
            if not os.path.exists(file):
                raise FileNotFoundError(f'File {file} not found')
            CUSTOM_DB.append(os.path.abspath(file))

    # Checks if the --species taxo exists. If yes, create a json object
    TAXO = uniprot.taxo(args.species)
    if (TAXO is None):
        raise ValueError(f"Taxo \"{args.species}\" not found.")
    
    EXCLUDE_TAXO = []
    if args.exclude:    
        for exclude in args.exclude:
            tax = uniprot.taxo(exclude)
            if (tax is None):
                raise ValueError(f"Excluded taxo \"{tax}\" not found.")
            EXCLUDE_TAXO.append(tax["taxonId"])

    MAX_TAXO = None        
    if args.max_taxo:
        MAX_TAXO = uniprot.taxo(args.max_taxo)
        if (MAX_TAXO is None):
            raise ValueError(f"MaxTaxo \"{args.max_taxo}\" not found.")
        else:
            MAX_TAXO = MAX_TAXO["taxonId"]
    
    ALL_RANK = ["forma", "varietas", "subspecies", "species", "species subgroup", "species group", "subgenus", "genus", "subtribe", "tribe", "subfamily", "family", "superfamily", "parvorder", "infraorder", "suborder", "order", "superorder", "subcohort", "cohort", "infraclass", "subclass", "class", "superclass", "subphylum", "phylum", "superphylum", "subkingdom", "kingdom", "superkingdom"]
    if args.max_rank:
        MAX_RANK = args.max_rank.lower()
        indexOfMR = ALL_RANK.index(MAX_RANK)
        MAX_RANK = ALL_RANK[indexOfMR:]
    else:
        indexOfMR = ALL_RANK.index("suborder")
        MAX_RANK = ALL_RANK[indexOfMR:]

    if args.cpus > os.cpu_count():
        raise ValueError(f"Error: You have provided {args.cpus} CPUs, but your machine has only {os.cpu_count()} CPUs available.")

    
    # Generate a unique ID for this run
    RUN_ID = str(uuid.uuid4())
               
    # Output directory
    OUTPUT_DIR = os.path.abspath(os.getcwd())
    if args.output_dir:
        parent_dir = os.path.dirname(args.output_dir)
        if not os.path.exists(parent_dir):
            raise FileNotFoundError(f"Directory {parent_dir} not found.")

        if not os.path.exists(args.output_dir):
            os.mkdir(args.output_dir)
        elif not os.path.isdir(args.output_dir):
            os.mkdir(args.output_dir)

        OUTPUT_DIR = os.path.abspath(args.output_dir)

    BLAST_TABLE_OUTPUT = OUTPUT_DIR + "/blast_results.xlsx"
    STATS_OUTPUT = OUTPUT_DIR + "/stats.txt"
    ID_MAPPING_OUTPUT = OUTPUT_DIR + "/identifier_mapping.txt"

    ANNOTATION_OUTPUT = OUTPUT_DIR + '/brownaming.fasta'
    if args.output_file:
        ANNOTATION_OUTPUT = OUTPUT_DIR + '/' + args.output_file
        if not args.output_file.endswith(('.fasta', '.faa', '.fa')):
            ANNOTATION_OUTPUT = ANNOTATION_OUTPUT + ".fasta"

    with open(OUTPUT_DIR + '/run_id.txt', 'w') as run_id_file:
        run_id_file.write(RUN_ID)

    # Create a directory with the name of the run ID and set it as the working directory
    WORKING_DIR = os.path.join(SCRIPT_DIR, "runs", RUN_ID)
    os.makedirs(WORKING_DIR)
    os.chdir(WORKING_DIR)
    
    makeJson("param.json", vars(args))
    STATE = {
        "input_customdb" : CUSTOM_DB,
        "input_taxo" : TAXO,
        "input_exclude_taxo" : EXCLUDE_TAXO,
        "input_max_taxo" : MAX_TAXO,
        "input_max_rank" : MAX_RANK,
        "input_output_dir" : OUTPUT_DIR  
    }
    makeJson(f"state.json", STATE)
    
# If it's a resume run
else:
    resume_dir = os.path.join(SCRIPT_DIR, 'runs', args.resume)
    if not os.path.isdir(resume_dir):
        raise ValueError(f"The resume working directory runs/{args.resume} was not found.")
    WORKING_DIR = resume_dir
    if 'resume' in vars(args) and any(v for k, v in vars(args).items() if k != 'resume'):
        warnings.warn("All parameters are ignored when you put --resume. It will use the same settings than the resume run.", UserWarning)
    os.chdir(WORKING_DIR)
    RUN_ID = args.resume
    param = {}
    with open("param.json", 'r') as param_file:
        param = json.load(param_file)
    args = argparse.Namespace(**param)
    args.resume = True
    PROTEINS = os.path.abspath(args.proteins)
    STATE = {}
    with open("state.json", 'r') as state_file:
        STATE = json.load(state_file)
        
    CUSTOM_DB = STATE["input_customdb"]
    TAXO = STATE["input_taxo"]
    EXCLUDE_TAXO = STATE["input_exclude_taxo"]
    MAX_TAXO = STATE["input_max_taxo"]
    MAX_RANK = STATE["input_max_rank"]
    OUTPUT_DIR = STATE["input_output_dir"]
    BLAST_TABLE_OUTPUT = OUTPUT_DIR + "/blast_results.xlsx"
    STATS_OUTPUT = OUTPUT_DIR + "/stats.txt"
    ID_MAPPING_OUTPUT = OUTPUT_DIR + "/identifier_mapping.txt"
    ANNOTATION_OUTPUT = OUTPUT_DIR + '/brownaming.fasta'
    if args.output_file:
        ANNOTATION_OUTPUT = OUTPUT_DIR + '/' + args.output_file
        if not args.output_file.endswith(('.fasta', '.faa', '.fa')):
            ANNOTATION_OUTPUT = ANNOTATION_OUTPUT + ".fasta"

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
    logger.info(f'Brownaming is resume')
else:
    logger.info(f'Brownaming start')
    
    
##### Start if the Brownaming pipeline

# 1. Build phylogenetic tree of the species (species-genus-family-order ...)
if not args.database:
    logger.info(f'Define the taxonId for each rank of the {args.species} taxonomy')
    FULL_LINEAGE = [
        {
            "scientificName" : TAXO["scientificName"].replace(" ","_"),
            "taxonId" : TAXO["taxonId"],
            "rank" : TAXO["rank"],
        }
    ]
    for i in range(len(TAXO["lineage"]) - 1, -1, -1):
        taxo_entry = TAXO["lineage"][i]
        FULL_LINEAGE.append(
            {
                "scientificName" : taxo_entry["scientificName"].replace(" ","_"),
                "taxonId" : taxo_entry["taxonId"],
                "rank" : taxo_entry["rank"],
            }
        )

    
# 2. Download proteins until the input maxRank (default maxRank = suborder)
DATABASES = []
  
if not args.database and "download_db_complete" not in STATE:
    logger.info(f'Download the database for the BLAST homology search')
    os.makedirs("database", exist_ok=True)
    lastStep = False
    start=0
    if "download_db_index" in STATE:
        logger.info(f'Download of databases was interrupted. Resuming where it left off.')
        start = STATE["download_db_index"]
        if "download_db_in_progress" in STATE:
            DATABASES = STATE["download_db_in_progress"]
    else:
        STATE["download_db_index"] = 0
        makeJson("state.json", STATE)

    for i in range(start, len(FULL_LINEAGE)):
        if (lastStep):
            break
        scientificName = FULL_LINEAGE[i]["scientificName"]
        taxonId = FULL_LINEAGE[i]["taxonId"]
        rank = FULL_LINEAGE[i]["rank"]
        logger.info(f"Try to download the uniprot database for {scientificName} ({rank}).")
        uniprot_fasta_filename = uniprot.downloadFasta(FULL_LINEAGE, i, EXCLUDE_TAXO) # Download all UniprotKB protein for the taxo
        logger.info(f"Completed for {scientificName} ({rank}).")
        if (rank in MAX_RANK or taxonId == MAX_TAXO):
            lastStep = True
        if (uniprot_fasta_filename != "NOPROT"):
            DATABASES.append(uniprot_fasta_filename) 
            STATE["download_db_in_progress"] = DATABASES
        STATE["download_db_index"] = i+1
        makeJson("state.json", STATE)
        
    STATE["download_db_complete"] = DATABASES
    makeJson("state.json", STATE)
    
else:
    if "download_db_complete" in STATE:
        DATABASES = STATE["download_db_complete"]
        logger.info(f'No need to download the databases because they are already downloaded in the previous run.')
    else: # Custom db have been provided:
        logger.info(f'No need to download the databases because you defined custom db in the input parameters.')
                  
           
# 3. Run blast
blast_reader_files = []

if "blast_reader_files_completed" in STATE:
    blast_reader_files = STATE["blast_reader_files_completed"]
    
else:
    if args.database:
        DATABASES = CUSTOM_DB
    
    start = 0
    if "blast_reader_files_index" in STATE:
        logger.info(f'BLAST homology searches were interrupted. Resuming where it left off.')
        start = STATE["blast_reader_files_index"]
        if "blast_reader_files_in_progress" in STATE:
            blast_reader_files = STATE["blast_reader_files_in_progress"]
    else:
        STATE["blast_reader_files_index"] = 0
        
    for i in range(start, len(DATABASES)):
        db = DATABASES[i]
        logger.info(f"Starting BLAST homology search against {db} database.")
        output = f"{os.path.basename(db)}_blast"
        if args.short:
            blast_parallel_file = blast.parallel_blast(
                protein_file=PROTEINS, 
                database_file=db, 
                output_file=output, 
                cpus=args.cpus,
                short=True
            )
        else:
            blast_parallel_file = blast.parallel_blast(
                protein_file=PROTEINS, 
                database_file=db, 
                output_file=output, 
                cpus=args.cpus,
                short=False
            )
        logger.info(f"Completed {db}_blast.")    
        
        if (blast_parallel_file != "NOMATCH"):
            blast_reader_files.append(blast_parallel_file)
            STATE["blast_reader_files_in_progress"] = blast_reader_files
        
        STATE["blast_reader_files_index"] = i+1
        makeJson("state.json", STATE)
            
    STATE["blast_reader_files_completed"] = blast_reader_files
    makeJson("state.json", STATE)

# 4. Output build
logger.info(f"Run Concentric searches using each BLAST result. Generating the outputs")
if "concentric_searches" not in STATE:
    concentric.concentric(blast_reader_files=blast_reader_files, 
                        fasta_file=PROTEINS, 
                        out_blast=BLAST_TABLE_OUTPUT, 
                        out_stats=STATS_OUTPUT, 
                        out_id_map=ID_MAPPING_OUTPUT, 
                        out_fasta=ANNOTATION_OUTPUT)
    STATE["concentric_searches"] = ANNOTATION_OUTPUT
    makeJson("state.json", STATE)
else:
    logger.info(f"Concentric searches have already be done in the previous run.")

# 5. Clear the working directory
if os.path.exists("blast"):
    shutil.rmtree("blast")
if os.path.exists("split"):
    shutil.rmtree("split")
if os.path.exists("database"):
    if args.database:
        shutil.rmtree("database")
    else:
        for file in os.listdir("database"):
            if not file.endswith("fasta"):
                os.remove(f"database/{file}") 
        
shutil.copytree(os.getcwd(), f"{OUTPUT_DIR}/Working_directory")
os.chdir("..")
shutil.rmtree(WORKING_DIR)
    
logger.info(f"Brownaming is completed, thank you for using it.")
