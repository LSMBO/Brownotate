import requests
import sys
import os

def download_uniprot(data):
    # Construct file name
    proteome_id = data["proteome_id"]
    species_name = data["scientific_name"]
    species_name_for_file = species_name.replace(' ', '_')
    file_name = f"evidence/{species_name_for_file}_{proteome_id}.faa"
    
    # Download the first page of the FASTA file
    response = get_url(data["url"])
    
    # Write the content of the first page to file
    write_fasta(response.text, file_name)
    
    # Check if there are more pages to download
    while response.links.get("next", {}).get("url"):
        # Download the next page of the FASTA file
        response = get_url(response.links["next"]["url"])
        
        # Append the content of the next page to file
        write_fasta(response.text, file_name)
    data["file_name"] = file_name
    return data
   
     
def get_url(url, **kwargs):
    # Sends a GET request to the given URL and returns the response object.
    response = requests.get(url, **kwargs)
    
    # Check if the response is OK (status code 200)
    if not response.ok:
        print("response not ok")
        response.raise_for_status()
        sys.exit()
    
    return response


def write_fasta(content, file_name):
    # Create directory if it doesn't exist
    if not os.path.exists("evidence"):
        os.makedirs("evidence")
        
    # Appends the given content to the end of the file with the given name.
    with open(file_name, "a") as f:
        f.write(content)
