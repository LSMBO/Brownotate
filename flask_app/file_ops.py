import os
import datetime
import zipfile
from flask import send_file, jsonify

def create_upload_folder():
    current_date = datetime.datetime.now().strftime("%d-%m-%Y")
    upload_folder = os.path.join('uploads', current_date)
    os.makedirs(upload_folder, exist_ok=True)
    return upload_folder

def handle_file_upload(files, upload_folder):
    file_paths = []
    for key in files:
        file = files[key]
        if file.filename == '':
            continue
        file_path = os.path.join(upload_folder, file.filename)
        try:
            file.save(file_path)
            file_paths.append(file_path)
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
                    zipf.write(file_path, os.path.relpath(file_path, rep_path))
        
        return send_file(zip_filename, as_attachment=True, download_name=os.path.basename(zip_filename))
    
    except FileNotFoundError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500