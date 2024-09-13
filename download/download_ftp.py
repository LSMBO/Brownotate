from ftp.ftp import connect_ftp, cwd_ftp, retrbinary_ftp
import gzip
import shutil
import os

def download_ftp(data, type):
    url = data["url"]

    # Extract the filename using the url
    file_name = url.split("/")[-1]
    file_path = type + "/" + url.split("/")[-1]

    # Extract dir
    dir = '/'.join(url.split("/")[:-1])
    dir = dir.replace(data['ftp'], '')
    # Try FTP login
    ftp = connect_ftp(data["ftp"])
    
    # Try FTP cwd
    cwd_ftp(ftp, dir)

    # Try file download
    retrbinary_ftp(ftp, "RETR " + file_name, file_name, type)

    ftp.quit()
    
    # Decompress the file
    with gzip.open(file_path, 'rb') as f_in:
        with open(file_path[:-3], 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Remove the compressed file
    os.remove(file_path)
    
    data["file_name"] = file_path[:-3]
    return data




    

    