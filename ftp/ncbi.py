from ftp.ftp import connect_ftp, cwd_ftp

def getDataFromFTP(ftp_url, data_type):    
    try:
        ftp = connect_ftp("ftp.ncbi.nlm.nih.gov")
        cwd_ftp(ftp, ftp_url)
        files = ftp.nlst()
        if data_type == "genome":
            for file in files:
                if file.endswith("genomic.fna.gz"):
                    ftp.quit()
                    return file
                
        elif data_type == "proteins":
            for file in files:
                if file.endswith("protein.faa.gz"):
                    ftp.quit()
                    return file

    except Exception as e:
        print(f"An error occurred: {e}")
    ftp.quit() 
    return {}
