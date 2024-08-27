from flask import Flask
from flask_cors import CORS
from flask_app.extensions import socketio
from flask_app.utils import load_config
from flask_app.routes.login import login_bp
from flask_app.routes.get_user_runs import get_user_runs_bp
from flask_app.routes.check_species_exists import check_species_exists_bp
from flask_app.routes.database_search import database_search_bp
from flask_app.routes.create_run import create_run_bp
from flask_app.routes.delete_run import delete_run_bp
from flask_app.routes.update_run_parameters import update_run_parameters_bp
from flask_app.routes.run_brownotate import run_brownotate_bp
from flask_app.routes.upload_file import upload_file_bp
from flask_app.routes.download_file import download_file_bp
from flask_app.routes.get_files import get_files_bp
from flask_app.routes.get_run import get_run_bp
from flask_app.routes.read_file import read_file_bp
from flask_app.routes.download_file_server import download_file_server_bp
from flask_app.routes.server_path import server_path_bp

app = Flask(__name__)
config = load_config()
app.config.from_mapping(config)
CORS(app)

socketio.init_app(app)

# Register blueprints
app.register_blueprint(login_bp)
app.register_blueprint(get_user_runs_bp)
app.register_blueprint(check_species_exists_bp)
app.register_blueprint(database_search_bp)
app.register_blueprint(create_run_bp)
app.register_blueprint(delete_run_bp)
app.register_blueprint(update_run_parameters_bp)
app.register_blueprint(run_brownotate_bp)
app.register_blueprint(upload_file_bp)
app.register_blueprint(download_file_bp)
app.register_blueprint(get_files_bp)
app.register_blueprint(get_run_bp)
app.register_blueprint(read_file_bp)
app.register_blueprint(download_file_server_bp)
app.register_blueprint(server_path_bp)