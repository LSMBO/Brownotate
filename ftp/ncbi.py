from ftp.ftp import cwd_ftp, connect_ftp, reconnect_ftp, display_time
import time

def getDataFromFTP(type, scientific_names, categories, bank):
    start_time = time.time()
    last_interaction_time = start_time
    priority_dirs = ["reference", "representative", "latest_assembly_versions"]
    data_type = ""
    url = ""
    quality = ""

    ftp = connect_ftp("ftp.ncbi.nlm.nih.gov")
    cwd_ftp(ftp, f"genomes/{bank}")
    base_path = ftp.pwd()

    current_index = 0
    directories_list = []
    for category in categories:
        cwd_ftp(ftp, category)
        directories_list.append(set(ftp.nlst()))
        cwd_ftp(ftp, base_path)

    while current_index < len(scientific_names):
        scientific_name = scientific_names[current_index]
        formatted_name = scientific_name.replace(" ", "_").lower().capitalize()
        
        if time.time() - last_interaction_time > 50:
            ftp = reconnect_ftp(ftp, "ftp.ncbi.nlm.nih.gov")
            cwd_ftp(ftp, f"genomes/{bank}")
            last_interaction_time = time.time()
        try:
            for category, directory_set in zip(categories, directories_list):       
                if formatted_name in directory_set:
                    cwd_ftp(ftp, f"{category}/{formatted_name}")
                    last_interaction_time = time.time()
                    for dir_name in priority_dirs:
                        if dir_name in ftp.nlst():
                            cwd_ftp(ftp, dir_name)
                            assemblies_data = []
                            ftp.dir(assemblies_data.append)

                            assemblies = [line.split()[-1] for line in assemblies_data if line.upper().startswith('D') or line.upper().startswith('L')]

                            for assembly in assemblies:
                                cwd_ftp(ftp, assembly)
                                files = ftp.nlst()
                                for file in files:
                                    if type == "genome":
                                        if file.endswith("genomic.fna.gz") and "rna_from_genomic" not in file and "cds_from_genomic" not in file:
                                            url = ftp.pwd() + "/" + file
                                            quality = dir_name
                                            data_type = "genome"
                                            print(f"NCBI_FTP Elapsed time : {display_time(time.time() - start_time)}. Found for {formatted_name}")
                                            ftp.quit()
                                            scientific_name = formatted_name.replace("_", " ")
                                            return {
                                                "url": url,
                                                "ftp": "ftp.ncbi.nlm.nih.gov",
                                                "data_type": data_type,
                                                "quality": quality,
                                                "database": bank,
                                                "scientific_name": scientific_name
                                            }
                                    else:
                                        if file.endswith("protein.faa.gz"):
                                            url = ftp.pwd() + "/" + file
                                            quality = dir_name
                                            data_type = "proteins"
                                            print(f"NCBI_FTP Elapsed time : {display_time(time.time() - start_time)}. Found for {formatted_name}")
                                            ftp.quit()
                                            scientific_name = formatted_name.replace("_", " ")
                                            return {
                                                "url": url,
                                                "ftp": "ftp.ncbi.nlm.nih.gov",
                                                "data_type": data_type,
                                                "quality": quality,
                                                "database": bank,
                                                "scientific_name": scientific_name
                                            }
                                cwd_ftp(ftp, base_path)
                cwd_ftp(ftp, base_path)
            current_index += 1

        except EOFError as e:
            print(f"EOFError encountered: {e}")
            ftp = reconnect_ftp(ftp, "ftp.ncbi.nlm.nih.gov")
            cwd_ftp(ftp, f"genomes/{bank}")
        except Exception as e:
            print(f"An error occurred: {e}")
            break

    ftp.quit()
    return {}
