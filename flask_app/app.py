from flask import Flask
from flask_cors import CORS
from flask_app.extensions import socketio
from flask_app.utils import load_config

from flask_app.routes.login import login_bp
from flask_app.routes.get_user_runs import get_user_runs_bp
from flask_app.routes.check_species_exists import check_species_exists_bp

from flask_app.routes.dbsearch.taxonomy import dbs_taxonomy_bp
from flask_app.routes.dbsearch.uniprot_proteome import dbs_uniprot_proteome_bp
from flask_app.routes.dbsearch.refseq import dbs_refseq_bp
from flask_app.routes.dbsearch.genbank import dbs_genbank_bp
from flask_app.routes.dbsearch.ensembl import dbs_ensembl_bp
from flask_app.routes.dbsearch.dnaseq import dbs_dnaseq_bp
from flask_app.routes.dbsearch.phylogeny import dbs_phylogeny_bp

from flask_app.routes.download.uniprot import download_uniprot_bp
from flask_app.routes.download.ensembl_ftp import download_ensembl_ftp_bp
from flask_app.routes.download.ncbi import download_ncbi_bp
from flask_app.routes.download.server import download_server_bp

from flask_app.routes.merge_fasta_files import merge_fasta_files_bp
from flask_app.routes.create_run import create_run_bp
from flask_app.routes.delete_run import delete_run_bp
from flask_app.routes.update_run_parameters import update_run_parameters_bp
from flask_app.routes.run_brownotate import run_brownotate_bp
from flask_app.routes.upload_file import upload_file_bp
from flask_app.routes.get_files import get_files_bp
from flask_app.routes.get_dbsearch import get_dbsearch_bp
from flask_app.routes.get_run import get_run_bp
from flask_app.routes.get_phylogeny_map import get_phylogeny_map_bp
from flask_app.routes.read_file import read_file_bp
from flask_app.routes.server_path import server_path_bp
from flask_app.routes.resume_run import resume_run_bp
from flask_app.routes.get_cpus import get_cpus_bp

app = Flask(__name__)
config = load_config()
app.config.from_mapping(config)
CORS(app)

socketio.init_app(app)

# Register blueprints
app.register_blueprint(login_bp)
app.register_blueprint(get_user_runs_bp)
app.register_blueprint(check_species_exists_bp)

app.register_blueprint(dbs_taxonomy_bp)
app.register_blueprint(dbs_uniprot_proteome_bp)
app.register_blueprint(dbs_refseq_bp)
app.register_blueprint(dbs_genbank_bp)
app.register_blueprint(dbs_ensembl_bp)
app.register_blueprint(dbs_dnaseq_bp)
app.register_blueprint(dbs_phylogeny_bp)

app.register_blueprint(download_uniprot_bp)
app.register_blueprint(download_ensembl_ftp_bp)
app.register_blueprint(download_ncbi_bp)
app.register_blueprint(download_server_bp)

app.register_blueprint(merge_fasta_files_bp)
app.register_blueprint(create_run_bp)
app.register_blueprint(delete_run_bp)
app.register_blueprint(update_run_parameters_bp)
app.register_blueprint(run_brownotate_bp)
app.register_blueprint(upload_file_bp)
app.register_blueprint(get_files_bp)
app.register_blueprint(get_dbsearch_bp)
app.register_blueprint(get_run_bp)
app.register_blueprint(get_phylogeny_map_bp)
app.register_blueprint(read_file_bp)
app.register_blueprint(server_path_bp)
app.register_blueprint(resume_run_bp)
app.register_blueprint(get_cpus_bp)
