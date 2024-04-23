from error_handling.ftp import cwd_ftp, connect_ftp
from . import uniprot


def getDataFromFTP(type, scientific_name):
    end_of_file = ["dna.primary_assembly.fa.gz", "dna.toplevel.fa.gz"]
    data_type = ""
    quality = ""
    if (type=="pep"):
        end_of_file = [".pep.all.fa.gz"]
    url = ""
    # Construct the base URL and scientific name in the appropriate format
    base_url = "pub/current_fasta/"
    scientific_name = scientific_name.replace(" ", "_").lower()
    # Try to connect to the Ensembl FTP server
    ftp = connect_ftp("ftp.ensembl.org")
        
    # Try FTP cwd
    cwd_ftp(ftp, base_url)

    # Check if the scientific name is a directory in the Ensembl FTP server
    if scientific_name in ftp.nlst():
        cwd_ftp(ftp, scientific_name)
        if type in ftp.nlst():
            cwd_ftp(ftp, type)
            files = ftp.nlst()
            
            # Loop through the files in the subdirectory
            for f in files:
                # If the file ends with end_of_file", set the proteins URL
                for end in end_of_file:
                    if f.endswith(end):
                        url = ftp.pwd() + '/' + f
                        if (type == "dna"):
                            data_type = "genome"
                            if (end == "dna.primary_assembly.fa.gz"):
                                quality = "primary assembly"
                            if (end == "dna.toplevel.fa.gz"):
                                quality = "toplevel"
                        if (type == "pep"):
                            data_type = "proteins"
                        break
    ftp.quit()
    scientific_name = scientific_name.replace("_", " ")
    return {
        "url" : url,
        "data_type" : data_type,
        "quality" : quality,
        "ftp" : "ftp.ensembl.org",
        "database" : "ensembl",
        "scientific_name" :  scientific_name
    }