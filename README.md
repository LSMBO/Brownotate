# Brownotate

Brownotate is an application designed for generating a protein sequence database for a given species. It can be run as a command-line tool or as a web application using Flask.

Before setting up your own Brownotate server, you can try a ***demo version*** without installing anything. Simply contact me at browna@unistra.fr, and I will create an account for you on the server hosted at my institute.

## Prerequisites

-**Operating System**: Linux (Ubuntu 22.04 or similar). Make sure to use a Linux server as Conda dependencies are not compatible with other operating systems.

## Installation

### Clone the Repository

First, clone the Brownotate repository:

```
git clone https://github.com/LSMBO/Brownotate.git
cd Brownotate
```

### Install Conda

If you do not have Conda installed, follow these steps to install it:

1. **Download Anaconda**:

```
wget https://repo.anaconda.com/archive/Anaconda3-2024.06-1-Linux-x86_64.sh
chmod +x Anaconda3-2024.06-1-Linux-x86_64.sh
./Anaconda3-2024.06-1-Linux-x86_64.sh
```

Follow the instructions to complete the installation:

-Read and accept the terms by typing 'yes'
-Choose the default installation location
-Confirm updating your shell profile to initialize Conda automatically

2. **Initialize Conda**:

```
conda init
```

### Create and Activate Conda Environments

Create and activate the required Conda environments:

For the br environment:

```
cd /path/to/Brownotate
conda env create -f environment_br.yml
```

For the sra-download environment:

```
cd /path/to/Brownotate
conda env create -f environment_sra_download.yml
```

### Configure MongoDB

1. **Download MongoDB Community Server:** 

Go to [MongoDB Community Download](https://www.mongodb.com/try/download/community), select:

- **Version**: 7.0.14 (current)  
- **Platform**: Ubuntu 22.04 x64  
- **Package**: Server  

*Or whichever matches your configuration.*

Click on **Download**.

2. **Install MongoDB:**

```
sudo dpkg -i mongodb-org-server_7.0.14_amd64.deb
```

3. **Start MongoDB:**

```
sudo systemctl start mongod
sudo systemctl status mongod
```

4. **Download MongoDB Shell:** 

Go to [MongoDB Shell Download](https://www.mongodb.com/try/download/shell), select:

-**Version:** 2.3.0
-**Platform:** Debian (10+) / Ubuntu (18.04+) x64
-**Package:** deb

*Or whichever matches your configuration.*

Click on **Download**.

5. **Install MongoDB Shell:**

```
sudo dpkg -i mongodb-mongosh_2.3.0_amd64.deb
```

6. **Configure MongoDB:**

```
mongosh
use brownotate-db
db.createCollection("users")
db.createCollection("dbsearch")
db.createCollection("runs")
db.createCollection("processes")
```

### Configure `config.json`

Edit the `config.json` file located in the root directory of the project:

```
{
  "email": "",
  "MONGO_URI": "",
  "BROWNOTATE_PATH": "",
  "BROWNOTATE_ENV_PATH": "",
  "SRA_DOWNLOAD_ENV_PATH": ""
}
```

- **`MONGO_URI`**: This follows the format `mongodb://<ip>:<port>/brownotate-db`. You can find the correct URI by running the `mongosh` command in your terminal. The IP is typically localhost and the port is usually 27017.
- **`BROWNOTATE_PATH`**: This should be the directory where you cloned the Brownotate repository.
- **`BROWNOTATE_ENV_PATH`**: Use the command `conda info --envs` to locate the path to the br Conda environment.
- **`SRA_DOWNLOAD_ENV_PATH`**: Use the command `conda info --envs` to locate the path to the sra-download Conda environment.

## Running Brownotate

1. **Web Application:**

To set up the Brownotate web application, you need to configure both the client from (https://github.com/LSMBO/brownotate-app) and the backend (https://github.com/LSMBO/Brownotate).
Brownotate
The web client for Brownotate is hosted in a separate repository. Follow the instructions in the Brownotate web client repository (https://github.com/LSMBO/brownotate-app) to install and configure the client. The client is responsible for interacting with the user and sending requests to the Brownotate backend.

Once the client is set up, you need to launch the Brownotate backend, which is a Flask-based server that handles requests from the client and executes commands. This backend is served using Gunicorn, a Python WSGI HTTP server optimized for handling concurrent connections. It has already been installed in the br Conda environment.

Use the following command to start the Flask server:

```
conda activate br
gunicorn -w 4 --worker-class eventlet --bind 0.0.0.0:8800 --timeout 2592000 run_flask:app 
```

The IP **0.0.0.0** allows the server to accept requests from any IP address. The port **8800** corresponds to the port on which the server listens for requests from the client.


2. ***Command-Line Interface:***

Brownotate offers a flexible command-line interface for genome annotation and protein database creation. Below are the main arguments and options:

### Basic Usage


- **`-s, --species`**: Name of the species (required, unless resuming a previous run).
- **`--run-id`**: Identifier of the run.
- **`--resume`**: Identifier of a run to resume if it was interrupted.
- **`-od, --output-dir`**: Path to the output directory (default: current directory).
- **`-c, --cpus`**: Number of CPUs to use (default: half of the available CPUs).

### Modes

- **`--dbs-only`**: Compute only the database search (dbs). Incompatible with several options like `--auto`, `--dna-sra`, etc.
- **`-a, --auto`**: Launch Brownotate in fully automatic mode, ignoring manual inputs for genome or sequencing data.
- **`--no-seq`**: Ignore sequencing data, can be used only with `--dbs-only` or `--auto`.
- **`--no-genome`**: Ignore genome data, compatible only with `--dbs-only` or `--auto`.
- **`--no-prots`**: Ignore protein data, only applicable with `--dbs-only`.

### Assembly Options

- **`-d, --dna-sra`**: SRA accession number of the DNA sequencing data.
- **`-dfile, --dna-file`**: Path to DNA FASTQ sequencing files. Use commas to separate paired files.
- **`--sra-bl`**: Blacklisted SRA accessions.
- **`--illumina-only`**: Run sequencing database search only on Illumina datasets.
- **`--skip-fastp`**: Skip the Fastp sequence filtering step.
- **`--skip-bowtie2`**: Skip the Bowtie2 step for removing PhiX reads.
- **`--skip-filtering`**: Skip both Fastp and Bowtie2 filtering steps.

### Annotation Options

- **`-g, --genome`**: Path to the input genome assembly file.
- **`-gu, --genome-url`**: URL to download the genome assembly (Ensembl/NCBI FTP).
- **`-e, --evidence`**: Path to the protein evidence database for annotation.
- **`-eu, --evidence-url`**: URL to download protein evidence (Uniprot, Ensembl/NCBI).
- **`--remove-included-sequences`**: Consider two proteins redundant if one is strictly included in the other.
- **`--skip-remove-redundancy`**: Skip the step of removing redundant protein sequences.
- **`-ml, --min-length`**: Augustus predicted sequences with a length below this threshold are removed from the annotation.

### BUSCO Options

- **`--skip-busco-assembly`**: Skip BUSCO evaluation of the assembly.
- **`--skip-busco-annotation`**: Skip BUSCO evaluation of the annotation.
- **`--skip-busco`**: Skip all BUSCO evaluations.

### Brownaming Options

- **`--skip-brownaming`**: Skip the Brownaming step of naming proteins.
- **`--brownaming-maxrank`**: Brownaming max rank for stopping blast comparisons.
- **`--brownaming-maxtaxo`**: Brownaming max taxo for stopping blast comparisons.
- **`--brownaming-exclude`**: Exclude specific taxa from Brownaming blast searches.
- **`--brownaming-db`**: Custom database (FASTA) for Brownaming blast comparisons.

### Example Commands

**Run in automatic mode for species "Homo sapiens":**

```
python /path/to/Brownotate/main.py -s "Homo sapiens" -a
```

**Run the database search (DBS) for "Homo sapiens" with a specific genome file:**

```
python /path/to/Brownotate/main.py -s "Homo sapiens" --dbs-only
```

**Run the database search (DBS) for "Mus musculus" by searching for sequencing only, and only Illumina sequencing:**

```
python /path/to/Brownotate/main.py -s "Mus musculus" --dbs-only --no-genome --no-proteins --only-illumina
```

**Run for Mus musculus with a custom genome assembly, skipping busco:**

```
python /path/to/Brownotate/main.py -s "Mus musculus" -g /path/to/mus_musculus_genome.fasta --skip-busco
```

**Run for Drosophila melanogaster (taxid: 7227) with 2 sequencing datasets from NCBI SRA database:**

```
python /path/to/Brownotate/main.py -s 7227 -d SRR30623762	-d SRR30623766	
```

**Resume a previous run:**

```
python /path/to/Brownotate/main.py --resume run_id
```


## Other scripts

- check_species_exists.py

Searches for the species in the UniprotKB Taxonomy database. If it exists, it displays its name and taxID like this "Staphylococcus aureus;1280". If it does not exist it raise an error.

Example:
```
python /path/to/Brownotate/check_species_exists.py -s "staphylococcus aureus"
```
- database_admin.py

Adds a user to the mongodb database. Works with -email and -password. If the email is already in the database, this changes the password.

Example:
```
python /path/to/Brownotate/database_admin.py -email test@email.com -password 48141514
```

Note: The password is encrypted using bcrypt before being stored in the database for added security.

- clear_working_dir.py

Proposes to delete old run working directories. Data can quickly accumulate, so a bit of tidying up from time to time is not a bad idea. Using input() methods, the script proposes to delete each run one after the other.

Example:
```
python /path/to/Brownotate/clear_working_dir.py
```
