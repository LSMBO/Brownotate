import subprocess
import os
import multiprocessing
import shutil

conda_bin_path = os.environ["CONDA_PREFIX"]+ "/bin"
scipio_script_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/ext"
      
def scipio(genome_files, evidence_file, flex=False):
    with multiprocessing.Pool() as pool:
        results = []
        for i, genome_file in enumerate(genome_files):
            work_dir = f"annotation/scipio_work_dir_{i+1}"
            os.makedirs(work_dir, exist_ok=True)
            shutil.copy(genome_file, work_dir+"/"+os.path.basename(genome_file))
            genome_file = os.path.basename(genome_file)
            
            if not flex:
                result = pool.apply_async(run_scipio, args=(genome_file, evidence_file, work_dir))
            else:
                result = pool.apply_async(run_flexible_scipio, args=(genome_file, evidence_file, work_dir))
            if result!="Failed":
                results.append(result)
 
        genesraw_files = []
        for result in results:
            if not os.path.exists(result.get()):
                print(f"Error at the end of scipio, in results={results}, the file {result} ({result.get()}) does not exist.")
                exit()
            genesraw_files.append(result.get())
        genesraw = "annotation/genes.raw.gb" 
        concatenate_files(genesraw_files, genesraw)
        clean(genome_files)
        return genesraw
        
def run_scipio(genome_file, evidence_file, work_dir):
    os.chdir(work_dir)
    max_blat_attempts = 3
    blat_attempt_count = 0
    while blat_attempt_count < max_blat_attempts and (not os.path.exists("scipio.yaml") or os.path.getsize("scipio.yaml") == 0):
        blat(genome_file, evidence_file) 
        blat_attempt_count += 1
    if not os.path.exists("scipio.yaml") or os.path.getsize("scipio.yaml") == 0:
        print(f"Warning : Failed to generate scipio.yaml after {max_blat_attempts} attempts for the one part of the genome {genome_file}.")
        return "Failed"
    if not os.path.exists("scipio.gff"):
        extract_gff_from_yaml()   
    if not os.path.exists("genes.raw.gb"):
        gff_to_genbank(genome_file) 
    return work_dir+"/genes.raw.gb"

def run_flexible_scipio(genome_file, evidence_file, work_dir):
    os.chdir(work_dir)
    max_blat_attempts = 3
    blat_attempt_count = 0
    while blat_attempt_count < max_blat_attempts and (not os.path.exists("scipio.yaml") or os.path.getsize("scipio.yaml") == 0):
        blat(genome_file, evidence_file, flex=True) 
        blat_attempt_count += 1
    if not os.path.exists("scipio.yaml"):
        print(f"Warning : Failed to generate scipio.yaml after {max_blat_attempts} attempts for the one part of the genome {genome_file}.")
        return "Failed"
    if not os.path.exists("scipio.gff"):
        extract_gff_from_yaml()
    if not os.path.exists("genes.raw.gb"):
        gff_to_genbank(genome_file) 
    return work_dir+"/genes.raw.gb"
        
def blat(genome_file, evidence_file, flex=False):
    if not flex:
        print(f"Run blat depuis {os.getcwd()}")
        command = f"{scipio_script_path}/scipio.1.4.1.pl --blat_output=prot.vs.genome.psl \"{genome_file}\" \"{evidence_file}\" > scipio.yaml"
    else:
        command = f"{scipio_script_path}/scipio.1.4.1.pl --blat_output=prot.vs.genome.psl --min_identity=50 --min_coverage=50 --min_score=0.2 \"{genome_file}\" \"{evidence_file}\" > scipio.yaml"
    print(f"({os.path.basename(os.getcwd())}) {command}")
    subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def extract_gff_from_yaml():
    if not os.path.exists("scipio.scipiogff") or os.path.getsize("scipio.scipiogff") == 0:
        command = f"cat scipio.yaml | {scipio_script_path}/yaml2gff.1.4.pl > scipio.scipiogff"
        print(f"({os.path.basename(os.getcwd())}) {command}")
        try:
            subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"({os.path.basename(os.getcwd())}) Error : scipio.scipiogff has not been generated: {e.stderr.decode()}")
    command = f"{conda_bin_path}/scipiogff2gff.pl --in=scipio.scipiogff --out=scipio.gff"
    print(f"({os.path.basename(os.getcwd())}) {command}")
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def gff_to_genbank(genome_file):
    command = f"{conda_bin_path}/gff2gbSmallDNA.pl scipio.gff {genome_file} 1000 genes.raw.gb"
    print(f"({os.path.basename(os.getcwd())}) {command}")
    subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def concatenate_files(input_files, output_file):
    with open(output_file, 'w') as outfile:
        for infile in input_files:
            with open(infile, 'r') as infile_handle:
                outfile.write(infile_handle.read())

def clean(genome_files):
    for i in range(len(genome_files)):
        work_dir = f"annotation/scipio_work_dir_{i+1}"
        shutil.rmtree(work_dir)
    