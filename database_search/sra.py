import sys, re, time
from Bio import Entrez
import xmltodict
import requests
from database_search.uniprot import UniprotTaxo
from . import ncbi

CONFIG = None

def getBetterSra(synonyms_scientific_names, taxonomy, sequencing_type, config, illumina_only, sra_blacklist):
    global CONFIG
    CONFIG = config
    top10 = {}
    exclude_ids = []
    
    is_group = False
    if taxonomy['lineage'][0]['rank'] not in ['species', 'subspecies', 'strain']:
        is_group = True
        
    for taxo in taxonomy['lineage']:
        if taxo['rank'] == 'genus':
            is_group = True
        
        if is_group:
            children = get_children(taxo['taxonId'], exclude_ids)
            children_taxids, children_scientific_names = zip(*children) if children else ([], [])
            exclude_ids += children_taxids
            top10 = getTop10Sra(children_scientific_names, sequencing_type, illumina_only=illumina_only, sra_blacklist=sra_blacklist)
            if top10:
                return top10            
        else:
            top10 = getTop10Sra(synonyms_scientific_names, sequencing_type, illumina_only=illumina_only, sra_blacklist=sra_blacklist)
            if top10:
                return top10
        
    return top10

      
def getTop10Sra(scientific_name_list, sequencing_type, max_bases=10**25, illumina_only=False, sra_blacklist=[]):
    record = sra_db_search(sequencing_type, scientific_name_list, illumina_only=illumina_only, sra_blacklist=sra_blacklist)
    # Check if any results were found
    if "IdList" in record:        
        best_entry_ids = record["IdList"]
        # Check if there are any entries in the results list
        if len(best_entry_ids) != 0:
            run_info_list = getRunInfoList(best_entry_ids) # run infos in a xml format
            # Initialize variables to hold the best entries information
            top_entries = []
            max_bases_list = []
            # Loop through the run information for each entry
            for entry in run_info_list:
                runs = getRuns(entry) # run infos convert in a dict [{run1_id : X, run1_platform: X, ...}, {run2}, ...]
                if not runs:
                    continue
                # Loop through the runs to find the ones with the most bases
                for run in runs:
                    if run['platform'] == "BGISEQ": # BGISEQ sequencing datasets do not work very well with Megahit 
                        continue
                    if (run['total_bases']):
                        total_bases = int(run['total_bases'])
                        if run["library_type"] == "paired":
                            total_bases *= 2
                        # If the run has more bases than the max_bases limit, it goes to the next run
                        if total_bases > max_bases:
                            continue
                        # If we haven't found 10 runs yet, add the current run to the list
                        if (len(max_bases_list) < 10) and (total_bases <= (max_bases-sum(max_bases_list))) :
                            top_entries.append(run)
                            max_bases_list.append(total_bases)
                        # It filters the better sequencing based on the number of base instead of the relevance 
                        else:
                            # Find the index of the lowest run in the top 10
                            min_index = max_bases_list.index(min(max_bases_list))
                            # Lower value
                            lower_value = sorted(max_bases_list)[0]
                            # Sum of the 9 highest values
                            top_nine_sum = sum(sorted(max_bases_list)[1:])                 
                            # If the current run has more bases than the lowest run in the top 10, replace it
                            if (total_bases > lower_value) and (total_bases <= (max_bases-top_nine_sum)):
                                top_entries[min_index] = run
                                max_bases_list[min_index] = total_bases

            # Sort the top_entries list by total_bases
            top_entries.sort(key=lambda x: int(x['total_bases']), reverse=True)
            
            # Add the rank and taxonID attribute to each entry
            for i in range(len(top_entries)):
                top_entries[i]['rank'] = i + 1
            # Convert the result list to a JSON object and return it
            for entry in top_entries:
                return {
                        'data_type' : sequencing_type.lower()+"seq",
                        'database' : 'sra',
                        'runs' : top_entries
                        }
            
            return {}

    return {}

def sra_db_search(library_strategy, scientific_name_list=None, accession=None, illumina_only=False, sra_blacklist=[]):
    # Set the email address for Entrez
    Entrez.email = CONFIG['email']
    term = ""
    combined_record = {
        'Count' : 0,
        'IdList' : []
    }

    if library_strategy == "RNA":
        term = f"\"biomol rna\"[Properties]"
    else: #library_strategy == "DNA"
        term = f"\"biomol dna\"[Properties]"
    
    term = f"{term} NOT DNBSEQ[Platform]"

    if illumina_only:
        term += f"{term} AND Illumina[Platform]"
    if sra_blacklist:
        term += f" NOT ({' OR '.join(sra_blacklist)})"

    # If accession is not None, it means that a specific sra entry is searched
    if accession:
        term_list = [f"{term} AND {accession}"]
    else:
        if scientific_name_list:
            term_list = []
            num_names = len(scientific_name_list)
            for i in range(0, num_names, 10):
                term_list.append(term)
                scientific_name_sublist = scientific_name_list[i:min(i+10, num_names)]
                term_list[-1] = f"{term_list[-1]} AND ({(' OR '.join([f'{name}[Organism]' for name in scientific_name_sublist]))})"

    for term in term_list:
        # Search SRA for sequencing data using the given search term
        
        try:
            search_handle = Entrez.esearch(db="sra",
                                        term=term,
                                        sort='relevance',
                                        idtype="acc",
                                        retmax=10000)
            record = Entrez.read(search_handle)
                
            if record["Count"] != '0':
                combined_record['Count'] += int(record["Count"])
                combined_record['IdList'].extend(record['IdList'])
                
            search_handle.close()
            
        except Exception as e:
            print("Connection to NCBI servers failed. Please try again later.", file=sys.stderr)
            print(e, file=sys.stderr)
            sys.exit(1)
    
    if combined_record["Count"]==0:
        return "Nothing"
        
    # If accession is not None, it means that a specific sra entry is searched. It is also directly return as a json
    if accession is not None:
        return jsonFromRecord(record, accession)
    return combined_record

def jsonFromRecord(record, accession=None):
    if "IdList" in record and len(record["IdList"]) == 1:
        entry = getRunInfoList(record["IdList"])[0]
        runs = getRuns(entry)
        if accession is not None:
            for run in runs:
                if (run["accession"]==accession):
                    return run
        return runs
              
def getRunInfoList(entry_list):
    # Build a comma-separated string of SRA entry IDs to query
    entry_ids = ','.join(entry_list)
        
    # Query the SRA database for summary information on each entry
    
    try:
        run_info_handle = Entrez.esummary(db="sra", id=entry_ids)
        run_info = Entrez.read(run_info_handle)
        run_info_handle.close()
    
    except Exception as e:
        print("Connection to NCBI servers failed. Please try again later.", file=sys.stderr)
        sys.exit(1)
        
    # Return the summary information for each entry as a list
    return run_info

def getRuns(entry):
    entry_id = entry["Id"]
    
    # Extract platform, title, and library type information from the experiment XML using regular expressions
    platform = re.search(r'<Platform.*?>(.*?)</Platform>', entry["ExpXml"]).group(1)
    title = re.search(r'<Title>(.*?)</Title>', entry["ExpXml"]).group(1)
    library_layout_str = re.search(r'<LIBRARY_LAYOUT(.*?)</LIBRARY_LAYOUT>', entry["ExpXml"]).group(1)
    scientific_name = re.search(r'ScientificName=\"(.*?)\"', entry["ExpXml"])
    organism_taxid = re.search(r'Organism taxid=\"(.*?)\"', entry["ExpXml"]).group(1)
    if scientific_name:
        scientific_name = scientific_name.group(1)
    else:
        scientific_name = UniprotTaxo.fetch_scientific_name_and_rank(organism_taxid)[0]
    # Determine the library type (paired-end, single-end, or none)
    library_type = ""
    if ("paired" in library_layout_str.lower()):
        library_type = "paired"
    elif ("single" in library_layout_str.lower()):
        library_type = "single"
    else:
        library_type = "none"
    
    # Extract the run information from the Runs section of the XML using regular expressions
    runs_list = re.findall(r'<Run .*?/>', entry["Runs"])
    runs = []
    
    for run_str in runs_list:
        run = xmltodict.parse(run_str)
        run_dict = {} 
                                       
        # Extract the accession and total bases for the run
        accession = run['Run']['@acc']
        total_bases = run['Run']['@total_bases']
                    
        # Add the run information to the result dictionary
        run_dict['entry_id'] = entry_id
        run_dict['platform'] = platform
        run_dict['title'] = title
        run_dict['library_type'] = library_type
        run_dict['accession'] = accession
        run_dict['total_bases'] = total_bases
        run_dict['scientific_name'] = scientific_name
        run_dict['taxid'] = organism_taxid
                                       
        # Add the result dictionary to the list of results
        runs.append(run_dict)
        return runs

def getSequencing(run_type, accession_list, config):
    global CONFIG
    CONFIG = config
    runs = []
    for acc in accession_list:
        runs.append(sra_db_search(run_type, accession=acc))
    return {"data_type": "dnaseq", "database": "sra", "runs": runs}

def get_children(taxid, exclude_ids=[]):
    childs = []
    url = f"https://rest.uniprot.org/taxonomy/search?query=(ancestor:{taxid})%20AND%20(rank:SPECIES%20OR%20rank:STRAIN%20OR%20rank:SUBSPECIES)&size=500&format=json"
    response = get_url(url)
    results = response.json()["results"]       
    for result in results:
        child_taxon_id = result['taxonId']
        if child_taxon_id not in exclude_ids:
            childs.append((child_taxon_id, result['scientificName']))

    while response.links.get("next", {}).get("url"):
        response = get_url(response.links["next"]["url"])
        results = response.json()["results"]
        for result in results:
            child_taxon_id = result["taxonId"]
            if child_taxon_id not in exclude_ids:
                childs.append((child_taxon_id, result['scientificName']))
    return childs

def get_url(url, max_attempts=3):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = requests.get(url)
            if response.ok:
                return response
            else:
                response.raise_for_status()
        except Exception as e:
            attempts += 1
            print(f"Attempt {attempts} failed for URL: {url}. Error: {e}")
            if attempts < max_attempts:
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"Max attempts reached. Failed to fetch URL: {url}")
                raise e

    return response

# Estimations:
# 1,000,000,000,000 --> 255.9Gb
# 300,000,000,000 --> 63.8Gb
# 100,000,000,000 --> 34,4Gb X
# 50,000,000,000 --> 11.2Go

