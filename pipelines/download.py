import gzip, os, shutil

def gunzip(file):
    with gzip.open(file, 'rb') as f_in:
        file_name = os.path.splitext(file)[0]
        with open(file_name, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(file)            
    return file_name


def run_download(data, download):
    data_type = data["data_type"] # dnaseq, genome, proteins
    database = data["database"] # sra, ensembl, genbank, refseq, uniprot

    if (database == "sra"):
        return download.download_sra(data)
    
    elif (database == "uniprot"):
        return download.download_uniprot(data)
    
    elif (data_type == "genome"):
        return download.download_ftp(data, "genome")
    
    else:
        res = download.download_ftp(data, "evidence")
        if res["file_name"].endswith(".gz"):
            res["file_name"] = gunzip(res["file_name"])
        return res
    