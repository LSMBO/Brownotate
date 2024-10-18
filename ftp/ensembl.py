from ftp.ftp import cwd_ftp, connect_ftp, reconnect_ftp, display_time
import time

def getDataFromFTP(type, scientific_names):
	start_time = time.time()
	last_interaction_time = start_time
	end_of_file = ["dna.primary_assembly.fa.gz", "dna.toplevel.fa.gz"]
	data_type = ""
	quality = ""
	if type == "pep":
		end_of_file = [".pep.all.fa.gz"]

	ftp = connect_ftp("ftp.ensembl.org")
	cwd_ftp(ftp, "/pub/current_fasta/")
	directories = set(ftp.nlst())
		
	current_index = 0
	while current_index < len(scientific_names):
		scientific_name = scientific_names[current_index]
		formatted_name = scientific_name.replace(" ", "_").lower()
  
		if time.time() - last_interaction_time > 120:
			ftp = reconnect_ftp(ftp, "ftp.ensembl.org")
			cwd_ftp(ftp, "/pub/current_fasta/")
			last_interaction_time = time.time()
		
		try:
			if formatted_name in directories:
				cwd_ftp(ftp, formatted_name)
				last_interaction_time = time.time()
				if type in ftp.nlst():
					cwd_ftp(ftp, type)
					files = ftp.nlst()

					for f in files:
						for end in end_of_file:
							if f.endswith(end):
								url = ftp.pwd() + '/' + f
								if type == "dna":
									data_type = "genome"
									quality = "primary assembly" if end == "dna.primary_assembly.fa.gz" else "toplevel"
								elif type == "pep":
									data_type = "proteins"
								print(f"ENSEMBL_FTP Elapsed time : {display_time(time.time() - start_time)}. Found for {formatted_name}")
								ftp.quit()
								return {
									"url": url,
									"data_type": data_type,
									"quality": quality,
									"ftp": "ftp.ensembl.org",
									"database": "ensembl",
									"scientific_name": scientific_name.replace("_", " ")
								}
			current_index += 1
		except EOFError as e:
			print(f"EOFError encountered: {e}")
			ftp = reconnect_ftp(ftp, "ftp.ensembl.org")
			cwd_ftp(ftp, "/pub/current_fasta/")
		except Exception as e:
			print(f"An error occurred: {e}")
			break
	ftp.quit()
	return {}

def getAssemblyFTPrepository(url, scientific_name):
	ftp = connect_ftp("ftp.ensembl.org")
	url = '/'.join(url.split('/')[:-2]) + '/dna'
	cwd_ftp(ftp, url)
	files = set(ftp.nlst())
	end_of_file = ["dna.primary_assembly.fa.gz", "dna.toplevel.fa.gz"]
	for f in files:
		for end in end_of_file:
			if f.endswith(end):
				url = ftp.pwd() + '/' + f
				quality = "primary assembly" if end == "dna.primary_assembly.fa.gz" else "toplevel"
				return {
					"url": url,
					"data_type": "genome",
					"quality": quality,
					"ftp": "ftp.ensembl.org",
					"database": "ensembl",
					"scientific_name": scientific_name
				}
	return {}
