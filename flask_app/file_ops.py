import os
import datetime
import zipfile
import shutil
import glob
from flask import send_file, jsonify

def create_wd_folder(run_id):
    wd_folder = os.path.join('runs', str(run_id))
    os.makedirs(wd_folder, exist_ok=True)
    return wd_folder

def create_upload_folder():
    current_date = datetime.datetime.now().strftime("%d-%m-%Y")
    upload_folder = os.path.join('uploads', current_date)
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder

def create_download_folder():
    cleanup_old_user_download_folders()
    current_date = datetime.datetime.now().strftime("%d-%m-%Y")
    download_folder = os.path.join('user_download', current_date)
    os.makedirs(download_folder, exist_ok=True)
    os.makedirs(os.path.join(download_folder, 'tmp'), exist_ok=True)
    return download_folder

def cleanup_old_user_download_folders(days_to_keep=30):
    base_folder = 'user_download'
    if not os.path.isdir(base_folder):
        return

    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
    for entry in os.listdir(base_folder):
        entry_path = os.path.join(base_folder, entry)
        if not os.path.isdir(entry_path):
            continue
        try:
            entry_date = datetime.datetime.strptime(entry, "%d-%m-%Y")
        except ValueError:
            # Ignore non-date directories like "tmp".
            continue
        if entry_date < cutoff_date:
            shutil.rmtree(entry_path, ignore_errors=True)

def move_wd_to_output_runs_folder(wd):
    current_date = datetime.datetime.now().strftime("%d-%m-%Y")
    source_folder = os.path.join('runs', wd)
    target_folder = os.path.join('output_runs', f"{current_date}_{wd}")
    os.makedirs(target_folder, exist_ok=True)
    for item in os.listdir(source_folder):
        item_path = os.path.join(source_folder, item)
        if os.path.isfile(item_path):
            os.rename(item_path, os.path.join(target_folder, item))
        elif os.path.isdir(item_path):
            os.rename(item_path, os.path.join(target_folder, item))
    os.rmdir(source_folder)
    cleanup_output_run_artifacts(target_folder)
    return target_folder


def cleanup_output_run_artifacts(output_run_path):
    if not os.path.isdir(output_run_path):
        return

    # Remove very large BUSCO intermediates that are not required to inspect results.
    ref_mpi_patterns = [
        os.path.join(output_run_path, 'stats', 'busco_genome', 'run_*_odb10', 'miniprot_output', 'ref.mpi'),
        os.path.join(output_run_path, 'stats', 'busco_annotation', 'run_*_odb10', 'miniprot_output', 'ref.mpi'),
    ]
    for pattern in ref_mpi_patterns:
        for ref_mpi_path in glob.glob(pattern):
            try:
                os.remove(ref_mpi_path)
            except OSError:
                pass

    # BUSCO lineage downloads are shared/re-downloadable and can dominate archive size.
    lineage_dir = os.path.join(output_run_path, 'stats', 'busco_downloads', 'lineages')
    if os.path.isdir(lineage_dir):
        shutil.rmtree(lineage_dir, ignore_errors=True)


def _skip_from_zip(rel_path):
    normalized = rel_path.replace('\\', '/')
    if normalized.endswith('/miniprot_output/ref.mpi'):
        return True
    if normalized.startswith('stats/busco_downloads/lineages/'):
        return True
    return False

def handle_file_upload(files, upload_folder):
    file_paths = []
    for key in files:
        file = files[key]
        if file.filename == '':
            continue
        file_path = os.path.join(upload_folder, file.filename)
        if os.path.exists(file_path):
            file_paths.append(f'"{file_path}"')
        else:
            try:
                file.save(file_path)
                file_paths.append(f'"{file_path}"')
            except Exception as e:
                print(f"Error saving file '{file.filename}' to '{file_path}': {str(e)}")
                return {'status': 'error', 'message': f"Failed to save file '{file.filename}'. Please try again."}, 500
    return file_paths

def download_zip(rep_path):
    try:
        if not os.path.isdir(rep_path):
            raise FileNotFoundError("Directory not found")
        zip_filename = f"{os.path.dirname(rep_path)}/{os.path.basename(rep_path)}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(rep_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, rep_path)
                    if _skip_from_zip(rel_path):
                        continue

                    # Avoid expensive recompression for already-compressed payloads.
                    lower = file.lower()
                    if lower.endswith(('.gz', '.zip', '.bz2', '.xz', '.7z')):
                        zipf.write(file_path, rel_path, compress_type=zipfile.ZIP_STORED)
                    else:
                        zipf.write(file_path, rel_path)
        
        return send_file(zip_filename, as_attachment=True, download_name=os.path.basename(zip_filename))
    
    except FileNotFoundError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500