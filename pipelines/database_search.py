import os
import json
import shutil
import datetime

STATE = None
DATABASE_SEARCH = None
LOGGER = None

def set_globals(state, database_search, logger, no_seq, no_genome, no_prots, search_similar_species):
    global STATE, DATABASE_SEARCH, LOGGER, NO_SEQ, NO_GENOME, NO_PROTS, SEARCH_SIMILAR_SPECIES
    STATE = state
    DATABASE_SEARCH = database_search
    LOGGER = logger
    NO_SEQ = no_seq
    NO_GENOME = no_genome
    NO_PROTS = no_prots
    SEARCH_SIMILAR_SPECIES = search_similar_species
    

def makeJson(title, object):
    with open(title, "w") as f:
        json.dump(object, f)

def displayJSON(path):
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            print(json.dumps(data, indent=4))
    except FileNotFoundError:
        print(f"Could not find {path}.")

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

def search_database():
    if os.path.exists("Database_Search.json"):
        with open("Database_Search.json", 'r') as database_search_file:
            search_data_res = json.load(database_search_file)
        LOGGER.info('Retrieved the different data from the Database_Search.json file.')
    else:
        search_data_res = DATABASE_SEARCH.all(STATE['scientific_name'], STATE['taxo'], STATE["args"]['illumina_only'], STATE["args"]['sra_bl'], STATE['config'], no_seq=NO_SEQ, no_genome=NO_GENOME, no_prots=NO_PROTS, search_similar_species=SEARCH_SIMILAR_SPECIES)
        makeJson("Database_Search.json", search_data_res)
        LOGGER.info(f"The database search with for {STATE['scientific_name']} are in the file Database_search.json")
    return search_data_res

def end_run():
    if "all_completed" in STATE:
        print(f"Brownotate was already completed. Your database search results are available in {STATE['output_directory']}/Database_search.json. Thank you for using Brownotate")
        LOGGER.info(f"Brownotate was already completed. Your database search results are available in {STATE['output_directory']}/Database_search.json. Thank you for using Brownotate")
    else:
        STATE["all_completed"] = "completed"
        makeJson("state.json", STATE)
        
        print(f"Brownotate is completed. Your database search results are available in {STATE['output_directory']}/Database_search.json. Thank you for using Brownotate")
        LOGGER.info(f"Brownotate is completed. Your database search results are available in {STATE['output_directory']}/Database_search.json. Thank you for using Brownotate")

        for handler in LOGGER.handlers:
            handler.close()
            LOGGER.removeHandler(handler)   

        copyWorkingDirectory()
        if not os.path.exists(os.path.join(STATE['output_fasta_filepath'], 'Database_search.json')):
            os.chdir("..")
            shutil.rmtree(STATE['run_id'])

        
        print(f"\nDatabase_search.json content :")
        displayJSON(os.path.join(STATE['output_directory'], "Database_Search.json"))
        exit()
        
def run_database_search(state, database_search, logger, dbs_only=False, no_seq=False, no_genome=False, no_prots=False, search_similar_species=False):
    set_globals(state, database_search, logger, no_seq, no_genome, no_prots, search_similar_species)
    logger.info(f"Search for the DNA sequencing, RNA sequencing, genomes and protein annotations for {STATE['scientific_name']} in different databases.")
    data = search_database()
    if dbs_only:
        end_run()
    print(f"\nDatabase_search.json content :")
    displayJSON(os.path.join(os.getcwd(), "Database_Search.json"))
    return data
