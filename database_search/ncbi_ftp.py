from error_handling.ftp import cwd_ftp, connect_ftp
from . import uniprot

def getDataFromFTP(type, scientific_name, categories, bank):
    # Format scientific name and set priority directories
    scientific_name = scientific_name.replace(" ", "_").lower().capitalize()
    priority_dirs = ["reference", "representative", "latest_assembly_versions"]
    data_type = ""
    url = ""
    quality = ""

    # Try to connect to NCBI FTP server
    ftp = connect_ftp("ftp.ncbi.nlm.nih.gov")

    # Try FTP cwd
    cwd_ftp(ftp, "genomes/"+bank)

    # Loop over categories and directories to find the genome
    for category in categories:
        # Attempt to change directory to the scientific name within the current category
        if (cwd_ftp(ftp, category+'/'+scientific_name, True, 2, 2)):
            # Check for the priority directories
            for dir_name in priority_dirs:
                # If the priority directory exists, select it and get a list of its contents
                if dir_name in ftp.nlst():
                    cwd_ftp(ftp, dir_name)
                    assemblies_data = []
                    ftp.dir(assemblies_data.append)
                    
                    # Select only the subdirectories from the list of contents
                    assemblies = [line.split()[-1] for line in assemblies_data if line.upper().startswith('D') or line.upper().startswith('L')]
                    
                    # Loop over the subdirectories to find the genome
                    for assembly in assemblies:
                        cwd = ftp.pwd()  # Sauvegarder le répertoire courant
                        cwd_ftp(ftp, assembly)
                        files = ftp.nlst()
                        for file in files:
                            # Look for the genomic sequence file, excluding any other types
                            if type=="genome":
                                if file.endswith("genomic.fna.gz") and "rna_from_genomic" not in file and "cds_from_genomic" not in file:
                                    url = ftp.pwd() + "/" + file
                                    quality = dir_name
                                    data_type = "genome"
                                    break
                            else:
                                if file.endswith("protein.faa.gz"):
                                    url = ftp.pwd() + "/" + file
                                    quality = dir_name
                                    data_type = "proteins"
                                    break
                        # Exit the assembly loop if the genome has been found
                        if url:
                            break
                        ftp.cwd(cwd) # Revenir au répertoire courant


                # Exit the priority directory loop if the genome has been found
                if url:
                    break
        # Exit the category loop if the genome has been found
        if url:
            break

    
    # Close the FTP connection
    ftp.quit()
    scientific_name = scientific_name.replace("_", " ")
    return {
        "url" : url,
        "ftp" : "ftp.ncbi.nlm.nih.gov",
        "data_type" : data_type, 
        "quality" : quality,
        "database" : bank,
        "scientific_name" :  scientific_name
    }