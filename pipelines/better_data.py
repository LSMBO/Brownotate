import os
import json

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
        
def run_better_data(data, database_search, logger):    
    better_data = database_search.betterData(data)
    logger.info(f'The most relevant data has been found and stored as \"better_data\".')
    makeJson("Better_data.json", better_data)
    print(f"\nBetter_data.json content :")
    displayJSON("Better_data.json")
    logger.info(f"The database search is completed.")
    return better_data
