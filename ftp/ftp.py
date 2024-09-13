import ftplib
import time
import sys
import os

def connect_ftp(ftp_name, retries=5, wait_seconds=10):
    attempt = 0
    connected = False
    ftp = None
    while attempt < retries and not connected:
        try:
            ftp = ftplib.FTP(ftp_name)
            ftp.login()
            connected = True
        except ftplib.all_errors as e:
            attempt += 1
            print(f"Failed to connect to {ftp_name}. Attempt {attempt}/{retries}.")
            print(f"Error message: {str(e)}")
            if attempt < retries:
                print(f"Waiting {wait_seconds} seconds before trying again...")
                time.sleep(wait_seconds)
    if not connected:
        print(f"Failed to connect to {ftp_name} after {retries} attempts. Exiting.")
        sys.exit(1)

    return ftp

def cwd_ftp(ftp, dir, testing=False, retries=5, wait_seconds=10):
    if testing:
        try:
            ftp.cwd(dir)
            return True
        except ftplib.all_errors as e:
            return False
    else:
        attempt = 0
        success = False
        while attempt < retries and not success:
            try:
                ftp.cwd(dir)
                success = True
            except ftplib.all_errors as e:
                attempt += 1
                print(f"Failed to connect to {dir}. Attempt {attempt}/{retries}.")
                print(f"Error message: {str(e)}")
                if attempt < retries:
                    print(f"Waiting {wait_seconds} seconds before trying again...")
                    time.sleep(wait_seconds)
        if not success:
            print(f"Failed to connect to {dir} after {retries} attempts. Exiting.")
            sys.exit(1)

def retrbinary_ftp(ftp, command, file_name, type, retries=5, wait_seconds=10):
    attempt = 0
    downloaded = False
    if not os.path.exists(type):
        os.makedirs(type)
    while attempt < retries and not downloaded:
        try:
            with open(type + "/" + file_name, "wb") as f:
                ftp.retrbinary(command, f.write)
                downloaded = True
        except Exception as e:
            attempt += 1
            print(f"Error occurred during file download in {ftp.pwd()}. Attempt {attempt}/{retries}.")
            print(f"Error message: {str(e)}")
            if os.path.exists(file_name):
                os.remove(file_name)
            if attempt < retries:
                print(f"Waiting {wait_seconds} seconds before trying again...")
                time.sleep(wait_seconds)

    if not downloaded:
        print(f"Failed to download file after {retries} attempts. Exiting.")
        sys.exit(1)

def reconnect_ftp(ftp, ftp_name):
    try:
        ftp.quit()
    except EOFError:
        print("EOFError during FTP quit, ignoring and reconnecting...")
    except Exception as e:
        print(f"Error during FTP quit: {e}, reconnecting...")
    time.sleep(10)
    return connect_ftp(ftp_name)

def display_time(elapsed_time):
    minutes, seconds = divmod(elapsed_time, 60)
    seconds, milliseconds = divmod(seconds, 1)
    return f"{int(minutes)}:{int(seconds):02}:{int(milliseconds * 1000):03}"
