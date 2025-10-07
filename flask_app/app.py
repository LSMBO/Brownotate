
# Core Flask and Extensions
from flask import Flask
from flask_cors import CORS
from flask_app.extensions import socketio
from flask_app.utils import load_config

# Database Search
from database_search.taxonomy import dbs_taxonomy_bp
from database_search.uniprot_proteome import dbs_uniprot_proteome_bp
from database_search.refseq import dbs_refseq_bp
from database_search.genbank import dbs_genbank_bp
from database_search.ensembl import dbs_ensembl_bp
from database_search.phylogeny import dbs_phylogeny_bp
from database_search.sra import dbs_dnaseq_bp, search_sequencing_run_bp

# Download
from download.uniprot import download_uniprot_bp
from download.ensembl import download_ensembl_ftp_bp
from download.ncbi import download_ncbi_bp
from download.server import download_server_bp
from download.sra import download_sra_bp

# Sequencing & Assembly
from sequencing.fastp import run_fastp_bp
from sequencing.phix import run_remove_phix_bp
from sequencing.megahit import run_megahit_bp

# Annotation & Stats
from annotation.prokka import run_prokka_bp
from annotation.brownaming import run_brownaming_bp
from annotation.remove_redundancy import run_remove_redundancy_bp
from annotation.remove_short_sequences import run_remove_short_sequences_bp
from annotation.split_assembly import run_split_assembly_bp
from annotation.scipio import run_scipio_bp
from annotation.model import run_model_bp
from annotation.optimize_model import run_optimize_model_bp
from annotation.augustus import run_augustus_bp
from stats.busco import run_busco_bp

# Utility Routes
from flask_app.routes.login import login_bp
from flask_app.routes.get_user_annotations import get_user_annotations_bp
from flask_app.routes.check_species_exists import check_species_exists_bp
from flask_app.routes.merge_fasta_files import merge_fasta_files_bp
from flask_app.routes.create_run import create_run_bp
from flask_app.routes.delete_run import delete_run_bp
from flask_app.routes.update_run_parameters import update_run_parameters_bp
from flask_app.routes.update_run import update_run_bp
from flask_app.routes.upload_file import upload_file_bp
from flask_app.routes.get_dbsearch import get_dbsearch_bp
from flask_app.routes.delete_dbsearch import delete_dbsearch_bp
from flask_app.routes.get_run import get_run_bp
from flask_app.routes.get_image import get_image_bp
from flask_app.routes.read_file import read_file_bp
from flask_app.routes.server_path import server_path_bp
from flask_app.routes.get_cpus import get_cpus_bp
from flask_app.routes.waiting_time_dbsearch import waiting_time_dbsearch_bp
from flask_app.routes.waiting_time_annotation import waiting_time_annotation_bp
from flask_app.routes.set_annotation_completed import set_annotation_completed_bp


app = Flask(__name__)
config = load_config()
app.config.from_mapping(config)
CORS(app)
socketio.init_app(app)

# Delete remaining processes in the database (in case of a crash)
from flask_app.database import delete
delete('processes', {})

# Database search
app.register_blueprint(dbs_taxonomy_bp)
app.register_blueprint(dbs_uniprot_proteome_bp)
app.register_blueprint(dbs_refseq_bp)
app.register_blueprint(dbs_genbank_bp)
app.register_blueprint(dbs_ensembl_bp)
app.register_blueprint(dbs_dnaseq_bp)
app.register_blueprint(dbs_phylogeny_bp)
app.register_blueprint(search_sequencing_run_bp)

# Download
app.register_blueprint(download_uniprot_bp)
app.register_blueprint(download_ensembl_ftp_bp)
app.register_blueprint(download_ncbi_bp)
app.register_blueprint(download_server_bp)
app.register_blueprint(download_sra_bp)

# Sequencing & Assembly
app.register_blueprint(run_fastp_bp)
app.register_blueprint(run_remove_phix_bp)
app.register_blueprint(run_megahit_bp)

# Annotation & Stats
app.register_blueprint(run_prokka_bp)
app.register_blueprint(run_brownaming_bp)
app.register_blueprint(run_remove_redundancy_bp)
app.register_blueprint(run_remove_short_sequences_bp)
app.register_blueprint(run_split_assembly_bp)
app.register_blueprint(run_scipio_bp)
app.register_blueprint(run_model_bp)
app.register_blueprint(run_optimize_model_bp)
app.register_blueprint(run_augustus_bp)
app.register_blueprint(run_busco_bp)

# Utility Routes
app.register_blueprint(login_bp)
app.register_blueprint(get_user_annotations_bp)
app.register_blueprint(check_species_exists_bp)
app.register_blueprint(merge_fasta_files_bp)
app.register_blueprint(create_run_bp)
app.register_blueprint(delete_run_bp)
app.register_blueprint(update_run_parameters_bp)
app.register_blueprint(update_run_bp)
app.register_blueprint(upload_file_bp)
app.register_blueprint(get_dbsearch_bp)
app.register_blueprint(delete_dbsearch_bp)
app.register_blueprint(get_run_bp)
app.register_blueprint(get_image_bp)
app.register_blueprint(read_file_bp)
app.register_blueprint(server_path_bp)
app.register_blueprint(get_cpus_bp)
app.register_blueprint(waiting_time_dbsearch_bp)
app.register_blueprint(waiting_time_annotation_bp)
app.register_blueprint(set_annotation_completed_bp)