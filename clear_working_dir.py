import shutil
import sys
import os

# This script deletes the working directories of Browntotate-1.2.0/runs and Browntotate-1.2.0/Brownaming-1.0.0/runs except for 
# the directory names specified in the command
# python clear_working_dir.py <directory name to excluse>

def prompt_user(dir, delete_all=False):
	parent = os.path.abspath(os.path.dirname(dir))
	if delete_all:
		return True
	response = input(f"\nDo you want to delete the directory {os.path.abspath(dir)}? [y] \n   'y' for yes\n   'n' for no\n   'a' for all: you accept to delete all directories in {parent}\n").strip().lower()
	if response == 'a':
		return 'a'
	elif response == 'y' or response == '':
		return True
	elif response == 'n':
		return False
	else:
		return prompt_user(dir)

delete_all_remaining = False
for dir in os.listdir("Brownaming-1.0.0/runs"):
	dir_path = os.path.join("Brownaming-1.0.0/runs", dir)
	if os.path.isdir(dir_path) and dir not in sys.argv:
		if delete_all_remaining:
			shutil.rmtree(dir_path)
			print(f"Deleted directory: {dir}")
		prompt = prompt_user(dir_path)
		if prompt == 'a':
			delete_all_remaining = True
			shutil.rmtree(dir_path)
			print(f"Deleted directory: {dir}")
		elif prompt:
			shutil.rmtree(dir_path)
			print(f"Deleted directory: {dir}")
  
delete_all_remaining = False
for dir in os.listdir("runs"):
	dir_path = os.path.join("runs", dir)
	if os.path.isdir(dir_path) and dir not in sys.argv:
		if delete_all_remaining:
			shutil.rmtree(dir_path)
			print(f"Deleted directory: {dir}")
		prompt = prompt_user(dir_path)
		if prompt == 'a':
			delete_all_remaining = True
			shutil.rmtree(dir_path)
			print(f"Deleted directory: {dir}")
		elif prompt:
			shutil.rmtree(dir_path)
			print(f"Deleted directory: {dir}")