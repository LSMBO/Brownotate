import re
from Bio import Entrez
import xmltodict

CONFIG = None

def getRunInfoList(entry_list):
    # Build a comma-separated string of SRA entry IDs to query
    entry_ids = ','.join(entry_list)
        
    # Query the SRA database for summary information on each entry
    run_info_handle = Entrez.esummary(db="sra", id=entry_ids)
    run_info = Entrez.read(run_info_handle)
    run_info_handle.close()
    
    # Return the summary information for each entry as a list
    return run_info

def getSequencing(run_type, accession_list, config):
    global CONFIG
    CONFIG = config
    runs = []
    for acc in accession_list:
        runs.append(sra_db_search(run_type, accession=acc))
    return {"data_type": "dnaseq", "database": "sra", "runs": runs}

def sra_db_search(library_strategy, scientific_name=None, accession=None, illumina_only=False, sra_blacklist=[]):
    # Set the email address for Entrez
    Entrez.email = CONFIG['email']
    # Build the search term based on the inputs
    if accession is not None:
        term = accession
    else:
        if library_strategy == "RNA":
            term = f"{scientific_name}[Organism] AND \"biomol rna\"[Properties]"
        elif library_strategy == "DNA":
            term = f"{scientific_name}[Organism] AND (\"biomol dna\"[Properties]"
        else:
            term = f"{scientific_name}[Organism]"
    
    # Add Illumina filter if illumina_only is True
    if illumina_only:
        term += " AND Illumina[Platform]"
    
    # Exclude accessions in the blacklist
    if sra_blacklist:
        term += f" NOT ({' OR '.join(sra_blacklist)})"
        
    # Search SRA for sequencing data using the given search term
    search_handle = Entrez.esearch(db="sra",
                                   term=term,
                                   sort='relevance',
                                   idtype="acc",
                                   retmax=500)
    record = Entrez.read(search_handle)
        
    if record["Count"]=="0":
        return "Nothing"
    search_handle.close()
    if accession is not None:
        return jsonFromRecord(record, scientific_name, accession)
    return record

def jsonFromRecord(record, scientific_name, accession=None):
    if "IdList" in record and len(record["IdList"]) == 1:
        entry = getRunInfoList(record["IdList"])[0]
        runs = getRuns(entry, scientific_name)
        if accession is not None:
            for run in runs:
                if (run["accession"]==accession):
                    return run
        return runs
        
# 1,000,000,000,000 --> 255.9Gb
# 300,000,000,000 --> 63.8Gb
# 100,000,000,000 --> 34,4Gb X
# 50,000,000,000 --> 11.2Go

def getTop10Sra(scientific_name, type, max_bases=100000000000, illumina_only=False, sra_blacklist=[]):
    record = sra_db_search(type, scientific_name, illumina_only=illumina_only, sra_blacklist=sra_blacklist)
    # Check if any results were found
    if "IdList" in record:        
        best_entry_ids = record["IdList"]
        
        # Check if there are any entries in the results list
        if len(best_entry_ids) != 0:
            run_info_list = getRunInfoList(best_entry_ids)
            # Initialize variables to hold the best entries information
            top_entries = []
            max_bases_list = []
            # Loop through the run information for each entry
            for entry in run_info_list:
                runs = getRuns(entry, scientific_name)
                if not runs:
                    continue
                # Loop through the runs to find the ones with the most bases
                for run in runs:
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
            # Add the rank attribute to each entry
            for i in range(len(top_entries)):
                top_entries[i]['rank'] = i + 1
            # Convert the result list to a JSON object and return it
            return top_entries

    return {}


def getBetterSra(scientific_name, type, illumina_only, sra_blacklist, config):
    global CONFIG
    CONFIG = config
    # Get top 10 sequencing runs for the given scientific name
    top10 = getTop10Sra(scientific_name, type, illumina_only=illumina_only, sra_blacklist=sra_blacklist)
    for entry in top10:
        # If the platform is Oxford Nanopore or PacBio SMRT, it return the sequencing as a JSON
        if entry["platform"] == "OXFORD_NANOPORE" or entry["platform"] == "PACBIO_SMRT":
            return {
                'data_type' : type.lower()+"seq",
                'database' : 'sra',
                'runs' : [entry]
            }
    return {
            'data_type' : type.lower()+"seq",
            'database' : 'sra',
            'runs' : top10
            }
               
def getRuns(entry, scientific_name):
    entry_id = entry["Id"]
         
    # Extract platform, title, and library type information from the experiment XML using regular expressions
    platform = re.search(r'<Platform.*?>(.*?)</Platform>', entry["ExpXml"]).group(1)
    title = re.search(r'<Title>(.*?)</Title>', entry["ExpXml"]).group(1)
    library_layout_str = re.search(r'<LIBRARY_LAYOUT(.*?)</LIBRARY_LAYOUT>', entry["ExpXml"]).group(1)
                
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
                                       
        # Add the result dictionary to the list of results
        runs.append(run_dict)
        return (runs)
        