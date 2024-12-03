import sys
import requests
from ftp import ncbi
from database_search.uniprot import UniprotTaxo

CONFIG = None

def get_headers(config=None):
    if config:
        email = config['email']
    else:
        email = CONFIG['email']
    
    return {
        "Email": email,
        "User-Agent": "Brownotate/1.0.0"
    }

def getTaxonID(scientific_name, config=None):
    headers = get_headers(config)
    
    params = {
        "db": "taxonomy",
        "term": scientific_name,
        "retmode": "json",
    }
    
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch"
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        taxon_ids = data.get("esearchresult", {}).get("idlist", [])
        if taxon_ids:
            return taxon_ids[0]
    except Exception as e:
        print("Connection to NCBI servers failed. Please try again later.", file=sys.stderr)
        sys.exit(1)

    return None

def exploreDatabase(data_type, scientific_names, bank):
    for scientific_name in scientific_names:
        term = f"{scientific_name}[Organism]"
        if data_type == "proteins":
            term += " AND has_annotation[filter]"
        if bank == "refseq":
            term += " AND has_annotation[filter] AND latest[filter]"

        headers = get_headers()
        
        params = {
            "db": "assembly",
            "term": term,
            "retmode": "json",
            "retmax": 10000,
        }
        
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch"
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            
            if ids:
                for assembly_id in ids:
                    results = fetchAssemblyDetails(assembly_id, data_type, bank)
                    if results:
                        return results
        except Exception as e:
            print("Connection to NCBI servers failed. Please try again later.", file=sys.stderr)
            sys.exit(1)
    return {}

def fetchAssemblyDetails(assembly_id, data_type, bank):    
    headers = get_headers()

    params = {
        "db": "assembly",
        "id": assembly_id,
        "retmode": "json",
    }

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary"
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        assembly_summary = data.get("result", {}).get(assembly_id, {})
        
        if assembly_summary:
            if bank == 'refseq' and assembly_summary.get("refseq_category") == 'na':
                return {}
            
            accessions = assembly_summary.get("synonym", {}).get(bank, None)
            ftp_path = assembly_summary.get(f"ftppath_{bank}", None)

            if ftp_path and accessions:
                ftp_path_split = ftp_path.split('/')
                ftp_url = '/'.join(ftp_path_split[3:])
                ftp_results = ncbi.getDataFromFTP(ftp_url, data_type)
                
                if ftp_results:
                    return {
                        "accession": accessions,
                        "entrez_id": assembly_id,
                        "url": f"{ftp_url}/{ftp_results}",
                        "ftp": "ftp.ncbi.nlm.nih.gov",
                        "data_type": data_type,
                        "database": bank,
                        "scientific_name": assembly_summary.get("speciesname"),
                    }
    except Exception as e:
        print("Connection to NCBI servers failed. Please try again later.", file=sys.stderr)
        sys.exit(1)
    
    return {}

def getBetterNCBI(scientific_name, taxonomy, bank, data_type, search_similar_species=False, config=None):
    global CONFIG
    CONFIG = config
    results = exploreDatabase(data_type, [scientific_name], bank)
    if not search_similar_species or "url" in results:
        if "url" in results:
            results["taxonId"] = getTaxonID(results["scientific_name"])  
        return results
    
    lineage_taxo_ids = [object['taxonId'] for object in reversed(taxonomy.get("lineage", []))]
    exclude_ids = []
    for taxo_id in lineage_taxo_ids:
        children = UniprotTaxo.fetch_children(taxo_id, exclude_ids, "scientificName")
        exclude_ids.extend(children)
        results = exploreDatabase(data_type, children, bank)
        if results:
            taxonId = getTaxonID(results["scientific_name"])
            results["taxonId"] = taxonId
            return results
    return {}
