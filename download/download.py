from .download_sra import download_sra
from .download_ftp import download_ftp
from .download_uniprot import download_uniprot
from .gunzip import gunzip

def download(better_data):
    data_type = better_data["data_type"] # dnaseq, rnaseq, genome, proteins
    database = better_data["database"] # sra, ensembl, genbank, refseq, uniprot

    if (database == "sra"):
        return download_sra(better_data)
    
    elif (database == "uniprot"):
        return download_uniprot(better_data)
    
    elif (data_type == "genome"):
        return download_ftp(better_data, "genome")
    
    else:
        res = download_ftp(better_data, "evidence")
        res["file_name"] = gunzip(res["file_name"])
        return res
