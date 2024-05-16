from error_handling.ftp import cwd_ftp, connect_ftp

def getDataFromFTP(type, scientific_names):
    end_of_file = ["dna.primary_assembly.fa.gz", "dna.toplevel.fa.gz"]
    data_type = ""
    quality = ""
    if type == "pep":
        end_of_file = [".pep.all.fa.gz"]

    # Connect to the Ensembl FTP server
    ftp = connect_ftp("ftp.ensembl.org")

    # Try to change directory to the base URL
    cwd_ftp(ftp, "pub/current_fasta/")
    directories = set(ftp.nlst())
    
    for scientific_name in scientific_names:
        formatted_name = scientific_name.replace(" ", "_").lower()
        # Check if the scientific name is a directory in the Ensembl FTP server
        if formatted_name in directories:
            cwd_ftp(ftp, formatted_name)
            if type in ftp.nlst():
                cwd_ftp(ftp, type)
                files = ftp.nlst()

                # Loop through the files in the subdirectory
                for f in files:
                    # If the file ends with end_of_file, set the proteins URL
                    for end in end_of_file:
                        if f.endswith(end):
                            url = ftp.pwd() + '/' + f
                            if type == "dna":
                                data_type = "genome"
                                if end == "dna.primary_assembly.fa.gz":
                                    quality = "primary assembly"
                                if end == "dna.toplevel.fa.gz":
                                    quality = "toplevel"
                            if type == "pep":
                                data_type = "proteins"
                            break
                ftp.quit()
                return {
                    "url": url,
                    "data_type": data_type,
                    "quality": quality,
                    "ftp": "ftp.ensembl.org",
                    "database": "ensembl",
                    "scientific_name": scientific_name.replace("_", " ")
                }

    ftp.quit()
    return {}
