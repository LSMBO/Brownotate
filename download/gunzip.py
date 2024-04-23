import gzip
import shutil
import os

def gunzip(file):
    with gzip.open(file, 'rb') as f_in:
        file_name = os.path.splitext(file)[0]
        with open(file_name, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(file)            
    return file_name
