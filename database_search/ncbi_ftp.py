from error_handling.ftp import cwd_ftp, connect_ftp
import time


def displayTime(elapsed_time):
    minutes, seconds = divmod(elapsed_time, 60)
    seconds, milliseconds = divmod(seconds, 1)
    return f"{int(minutes)}:{int(seconds):02}:{int(milliseconds * 1000):03}"



def getDataFromFTP(type, scientific_names, categories, bank):
    start_time = time.time()
    # Format scientific name and set priority directories
    priority_dirs = ["reference", "representative", "latest_assembly_versions"]
    data_type = ""
    url = ""
    quality = ""

    # Try to connect to NCBI FTP server
    ftp = connect_ftp("ftp.ncbi.nlm.nih.gov")

    # Try FTP cwd
    cwd_ftp(ftp, "genomes/"+bank)
    for scientific_name in scientific_names:
        formatted_name = scientific_name.replace(" ", "_").lower().capitalize()
        initial_cwd = ftp.pwd()
        # Loop over categories and directories to find the genome
        for category in categories:
            # Attempt to change directory to the scientific name within the current category
            if (cwd_ftp(ftp, category+'/'+formatted_name, True, 2, 2)):
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
                                        print(f"NCBI_FTP Elapsed time : {displayTime(time.time() - start_time)}. Found for {formatted_name}")
                                        ftp.quit()
                                        scientific_name = formatted_name.replace("_", " ")
                                        return {
                                            "url" : url,
                                            "ftp" : "ftp.ncbi.nlm.nih.gov",
                                            "data_type" : data_type, 
                                            "quality" : quality,
                                            "database" : bank,
                                            "scientific_name" : scientific_name
                                        }
                                else:
                                    if file.endswith("protein.faa.gz"):
                                        url = ftp.pwd() + "/" + file
                                        quality = dir_name
                                        data_type = "proteins"
                                        print(f"NCBI_FTP Elapsed time : {displayTime(time.time() - start_time)}. Found for {formatted_name}")
                                        ftp.quit()
                                        scientific_name = formatted_name.replace("_", " ")
                                        return {
                                            "url" : url,
                                            "ftp" : "ftp.ncbi.nlm.nih.gov",
                                            "data_type" : data_type, 
                                            "quality" : quality,
                                            "database" : bank,
                                            "scientific_name" : scientific_name
                                        }
                            ftp.cwd(cwd)
            ftp.cwd(initial_cwd)

    # Close the FTP connection
    print(f"NCBI_FTP Elapsed time : {displayTime(time.time() - start_time)}. Nothing found")
    ftp.quit()
    return {}
    