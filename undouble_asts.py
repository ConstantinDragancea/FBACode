import fabric
import os
import tempfile
import tarfile
import os
import sys
import traceback
import shutil
import glob
import concurrent
import json
import time
import random

from fabric import Connection
from paramiko import SSHException
from os.path import join, exists, basename
from time import sleep, time

BASE_PATH = "/home/cdragancea/runs_archived"
LOCAL_AST_ARCHIVE = "/home/cdragancea/ast_archives_undoubling"
DESTINATION_FOLDER = "/spclstorage/cdragancea/builds_archive/undoubled_build_folder"
THREADS_COUNT = 1

PROJECT_BLACKLIST = [
    "telegram-desktop", # done
    "ifcplus", # done
    "seqan",
    "ball", # done
    "trilinos", # done
    "kicad",
    "quantlib",
    "cvc4", # done
    "vtk9", # done
    "cegui", # done
    "late" # done
]

def recursively_get_files(directory, ext = ""):
    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(ext):
                files.append(join(root, filename))
    return files

def delete_non_cpp_files(path):
    FILE_WHITELIST = [".cpp", ".h", ".hpp", ".c", ".cc", ".cp", ".hh", ".cxx", ".hxx", ".c++", ".h++", ".inc", ".i", ".ii", ".C", ".H", ".CPP", ".HPP", ".CXX", ".HXX", ".C++", ".H++", ".INC", ".I", ".II", ".CP", "output.json", ".log"]
    files = recursively_get_files(path)
    nr_removed_files = 0
    for file in files:
        if not any([file.endswith(ext) for ext in FILE_WHITELIST]):
            os.remove(file)
            nr_removed_files += 1
    return nr_removed_files

def remove_empty_directories(path):
    flag = True
    nr_removed_dirs = 0
    while flag:
        flag = False
        for root, dirs, filenames in os.walk(path, topdown = False):
            for dir in dirs:
                try:
                    os.rmdir(join(root, dir))
                    flag = True
                    nr_removed_dirs += 1
                except Exception as e:
                    # print(f"Directory is probably not empty")
                    pass
                    # print(f"TRACEBACK: {traceback.format_exc()}")
    return nr_removed_dirs

def try_put_multiple_times(local, remote, max_tries = 3):
    while max_tries > 0:
        try:
            with Connection(host = 'spclstorage.inf.ethz.ch', user = "cdragancea") as conn:
                conn.put(local = local, remote = remote)
        except PermissionError as e:
            print(f"An error occurred while uploading to remote server: {e}")
            # print(f"TRACEBACK: {traceback.format_exc()}")
            # return False, archive_name
            remote_file_size = int(conn.run(f"stat -c %s {remote}", hide = True).stdout.strip())
            local_file_size = os.path.getsize(local)

            if remote_file_size != local_file_size:
                print("Failed to upload build artifacts to remote storage server")
                print(f"src = {local} dst = {remote}")

                print(f"Exception: {e}")
                print(f"Traceback: {traceback.format_exc()}")
                max_tries -= 1
                continue
                
            break
        except SSHException as e:
            print(f"SSHException error occured for {basename(local)}")
            max_tries -= 1
            continue
        except:
            max_tries -= 1
            continue
    return True

def undouble_ast_files(temp_dir_all_archives, path_to_archive):
    archive_temp_dir = tempfile.mkdtemp(dir="/home/cdragancea/FBACode", prefix="temp_undoubling_unarchive_")
    print(f"Temp dir for extracting the archive: {archive_temp_dir} for {basename(path_to_archive)}")
    new_archive = None
    try:
        print(f"Extracting files from archive {basename(path_to_archive)}")
        with tarfile.open(path_to_archive, "r:gz") as tar:
            tar.extractall(path = archive_temp_dir)
        
        if exists(path_to_archive):
            os.remove(path_to_archive)
        print(f"Finished extracting. Removing files...")
        # nr_removed_files = 0
        # ast_files_in_build = glob.glob(join(archive_temp_dir, "build", "**/*.ast"), recursive = True)
        # for file in ast_files_in_build:
        #     os.remove(file)
        #     nr_removed_files += 1
        nr_removed_files = delete_non_cpp_files(join(archive_temp_dir, "build"))
        nr_removed_dirs = remove_empty_directories(join(archive_temp_dir, "build"))
        
        print(f"Removed {nr_removed_files} files from archive {basename(path_to_archive)}.")
        print(f"Removed {nr_removed_dirs} empty directories from archive {basename(path_to_archive)}.")
        print("Making new archive...")

        ast_files = glob.glob(join(archive_temp_dir, "compiler_output/AST", "**/*.ast"), recursive = True)
        with open(join(archive_temp_dir, "build", "output.json"), "r") as f:
            project = json.loads(f.read())
        project["project"]["build"]["nr_asts"] = len(ast_files)
        project["project"]["ast_files"]["nr_asts"] = len(ast_files)

        with open(join(archive_temp_dir, "build", "output.json"), "w") as f:
            f.write(json.dumps(project, indent = 2))

        # make new archive
        with tarfile.open(join(temp_dir_all_archives, basename(path_to_archive)), "w:gz") as tar:
            tar.add(join(archive_temp_dir, "build"), arcname = "build")
            tar.add(join(archive_temp_dir, "compiler_output"), arcname = "compiler_output")
        new_archive = join(temp_dir_all_archives, basename(path_to_archive))
    except Exception as e:
        print(f"An error occurred: {e}")
        print(f"TRACEBACK: {traceback.format_exc()}")
    
    if exists(archive_temp_dir):
        try:
            shutil.rmtree(archive_temp_dir)
        except Exception as e:
            print(f"failed to delete the extraction temp dir for {basename(path_to_archive)}")
    
    return new_archive

def worker_func(target_folder, temp_dir, archive_name):
    print(f"Worker func called with target_folder={target_folder}, temp_dir={temp_dir}, archive_name={archive_name}")

    try:
        with Connection(host = 'spclstorage.inf.ethz.ch', user = "cdragancea") as conn:
            remote_file_size = int(conn.run(f"stat -c %s {join(target_folder, archive_name)}", hide = True).stdout.strip())
    except:
        return False, archive_name

    # if remote_file_size > 20 * 1024 * 1024 * 1024:
    #     print(f"File {archive_name} is too large. Skipping...")
    #     return False, archive_name

    try:
        with Connection(host = 'spclstorage.inf.ethz.ch', user = "cdragancea") as conn:
            conn.get(remote = join(target_folder, archive_name), local = join(temp_dir, archive_name))
    except Exception as e:
        print(f"An error occurred: {e}")
        print(f"TRACEBACK: {traceback.format_exc()}")
        return False, archive_name

    new_archive = undouble_ast_files(temp_dir, join(temp_dir, archive_name))
    if new_archive is None:
        
        return False, archive_name

    print(f"Made new archive {archive_name} with clean build dir. Uploading to remote server...")
    success = try_put_multiple_times(local = new_archive, remote = join(DESTINATION_FOLDER, f"{basename(new_archive)}"))
    
    if not success:
        return False, archive_name

    print(f"Removing old and new archive from local server of project {archive_name}")
    if exists(new_archive):
        os.remove(new_archive)
    if exists(join(temp_dir, archive_name)):
        os.remove(join(temp_dir, archive_name))
    
    return True, archive_name

def main():
    target_folder = join(BASE_PATH, sys.argv[1])
    temp_dir = tempfile.mkdtemp(dir="/home/cdragancea/FBACode", prefix="temp_undoubling_download_")
    print(f"Temp dir for storing the initial archive: {temp_dir}")
    # threads_count = 16

    undoubled_asts = dict()
    try:
        with open("undoubled_asts.json", "r") as f:
            undoubled_asts = json.loads(f.read())
    except FileNotFoundError:
        pass

    try:
        with Connection(host = 'spclstorage.inf.ethz.ch', user = "cdragancea") as conn:
            file_exists = conn.run(f"test -d {target_folder} && echo True || echo False", hide = True).stdout.strip()
            if file_exists == "False":
                print(f"Folder {target_folder} does not exist on the remote machine")
                return
        
            file_list = conn.run(f"ls {target_folder}", hide = True).stdout.strip().split("\n")
    except Exception as e:
        print(f"An error occurred: {e}")
        print(f"TRACEBACK: {traceback.format_exc()}")
    
    file_list = [basename(file) for file in file_list if file.endswith(".tar.gz")]
    file_list = [basename(file) for file in file_list if not file.startswith("testt_")]
    file_list = [file for file in file_list if file not in undoubled_asts or undoubled_asts[file] == False]
    file_list = [file for file in file_list if not any([project in file for project in PROJECT_BLACKLIST])]

    # shuffle file_list
    random.shuffle(file_list)

    with concurrent.futures.ProcessPoolExecutor(THREADS_COUNT) as pool:
        futures = []
        idx = 0
        start = time()

        jobs_left = len(file_list)
        # jobs_left = min(jobs_left, 20)
        
        while len(futures) < min(THREADS_COUNT, len(file_list)):
            project_name = file_list[idx]
            
            futures.append(pool.submit(
                worker_func,
                # (
                    target_folder,
                    temp_dir,
                    project_name, 
                # )
            ))
            idx += 1
            sleep(0.5) # each worker func runs an ssh connection to the storage server. too many connections at once cause the server to refuse the connection

        # incomplete_futures = True
        # when one finishes, increment counter and add a new one to the queue
        while jobs_left > 0:
            completed_futures, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)

            for future in completed_futures:
                success, project_name = future.result()
                futures.remove(future)

                undoubled_asts[project_name] = success
                
                with open("undoubled_asts.json", "w") as f:
                    f.write(json.dumps(undoubled_asts, indent = 2))

                jobs_left -= 1
                if jobs_left % 5 == 0:
                    print(f"{jobs_left} AST undouble jobs left")
            
                while idx < len(file_list) and len(futures) < THREADS_COUNT:
                    project_name = file_list[idx]
                    futures.append(pool.submit(
                        worker_func,
                        # (
                            target_folder,
                            temp_dir,
                            project_name, 
                        # ),
                    ))
                    idx += 1
                    sleep(0.5) # each fetch runs an ssh connection to the storage server. too many connections at once cause the server to refuse the connection
        end = time()

        # saving the results

        print(f"Analyzed {len(file_list)} projects in {end - start} [s]")
    
    if exists(temp_dir):
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()