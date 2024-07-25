import sys
import os
import importlib
import glob
import subprocess
from subprocess import PIPE
import json

from time import time
from shutil import move, copyfile
from datetime import datetime
from os.path import basename

from utils.driver import open_logfiles, recursively_get_files, recursively_get_dirs  # type: ignore
from build_systems.utils import run  # type: ignore

DOCKER_MOUNT_POINT = "/home/fba_code"

# OMIT_ERRORS_ARGS=""

# OMIT_ERRORS_ARGS+=("-Wno-error=implicit-function-declaration")
# OMIT_ERRORS_ARGS+=("-Wno-error=implicit-int")
# OMIT_ERRORS_ARGS+=("-Wno-error=int-conversion")
# OMIT_ERRORS_ARGS+=("-Wno-error=incompatible-function-pointer-types")
# OMIT_ERRORS_ARGS+=("-Wno-error=narrowing")
# OMIT_ERRORS_ARGS+=("-Wno-error=strict-prototypes")
# OMIT_ERRORS_ARGS+=("-Wno-error=unused-but-set-variable")
# OMIT_ERRORS_ARGS+=("-Wno-error=enum-constexpr-conversion")

ERRORS_TO_OMIT_FLAGS = [
    "-Wno-error=implicit-function-declaration",
    "-Wno-error=implicit-int",
    "-Wno-error=int-conversion",
    "-Wno-error=incompatible-function-pointer-types",
    "-Wno-error=narrowing",
    "-Wno-error=strict-prototypes",
    "-Wno-error=unused-but-set-variable",
    "-Wno-error=enum-constexpr-conversion",
]

def get_folder_size(folder_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath):  # Check if it's a file (skip if it's a symlink)
                total_size += os.path.getsize(filepath)
    return total_size

class Context:
    def __init__(self, cfg):
        self.cfg = cfg

    def set_loggers(self, out, err):
        self.out_log = out
        self.err_log = err


def print_section(idx, ctx, message):
    hashtags = "#" * (len(message) + 4)
    to_print = "\n{0}\n# {1} #\n{0}".format(hashtags, message)
    ctx.err_log.print_info(idx, to_print)
    ctx.out_log.print_info(idx, to_print)
    print(f"[IDX {idx}]: {to_print}", flush = True)

def run_command(cmd, cwd, capture_output = False, text = False, stdout = None, stderr = None):
    print_section(idx, ctx, "running command: {}".format(" ".join(cmd)))
    ret = run(cmd, cwd=cwd, capture_output = capture_output, text = text)
    if ret.returncode:
        print(f"Failed to run command '{cmd}', got return code: {ret.returncode}")
        # ctx.err_log.print_error(idx, "stderr: {}".format(ret.stderr))
        # ctx.out_log.print_info(idx, "stdout: {}".format(ret.stdout))
        # print(f"[IDX {idx}]: stdout: {ret.stdout}")
        # print(f"[IDX {idx}]: stderr: {ret.stderr}")
    ctx.out_log.print_info(idx, f"command '{cmd}' ran successfully!")
    print(f"[IDX {idx}]: command '{cmd}' ran successfully!", flush = True)
    return ret

# TODO: this is hardcoded. Make it configurable
ast_dir = f"{DOCKER_MOUNT_POINT}/compiler_output/AST"
results_dir = f"{DOCKER_MOUNT_POINT}/analyze"
external_results_dir = os.environ.get("RESULTS_DIR", "")
analyses_to_run = os.environ.get("ANALYSES", "")  # TODO: validate analysis names

json_input = json.load(open(sys.argv[1], "r"))
idx = json_input["idx"]
name = json_input["name"]
# verbose = json_input["verbose"]

# directories to be chowned in the end
chown_dirs = [results_dir]

cfg = {"output": {"verbose": True, "file": results_dir}}
ctx = Context(cfg)

timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
loggers = open_logfiles(cfg, name.replace("/", "_"), timestamp=timestamp)

# chown the logfiles

# get the uid and gid of the host user through the results dir which was created before entering the container
host_uid = os.stat(results_dir).st_uid
host_gid = os.stat(results_dir).st_gid

for file in glob.glob("*.log"):
    print("chowning {}...".format(file))
    out = subprocess.run(["chown", "-R", "{}:{}".format(host_uid, host_gid), file])
    if out.returncode != 0:
        print(out, flush = True)

ctx.set_loggers(loggers.stdout, loggers.stderr)

# Updated -> Configure
project = {
    # "status": "configure",
    "analyze": {
        "dir": external_results_dir,
        "stdout": os.path.basename(loggers.stdout_file),
        "stderr": os.path.basename(loggers.stderr_file),
        "installed": [],
        "-j": os.environ.get("JOBS", 1),
    },
}

decompress_start = time()

# untar the archive
ret = run_command(["tar", "-xzf", f"{DOCKER_MOUNT_POINT}/ast_archive/{name}.tar.gz"], cwd=DOCKER_MOUNT_POINT)

decompress_end = time()

if 'size_statistics' not in project:
    project['size_statistics'] = dict()
project['size_statistics']['decompression_time'] = decompress_end - decompress_start
project['size_statistics']['nr_ast_files'] = len(recursively_get_files(os.path.join(DOCKER_MOUNT_POINT, "compiler_output", "AST"), ext=".ast"))
project['size_statistics']['nr_bc_files'] = len(recursively_get_files(os.path.join(DOCKER_MOUNT_POINT, "compiler_output", "bitcodes"), ext=".bc"))
project['size_statistics']['ast_size'] = get_folder_size(os.path.join(DOCKER_MOUNT_POINT, "compiler_output", "AST"))
project['size_statistics']['bc_size'] = get_folder_size(os.path.join(DOCKER_MOUNT_POINT, "compiler_output", "bitcodes"))

# remove archive
# os.remove(f"{DOCKER_MOUNT_POINT}/ast_archive/{name}.tar.gz")

# installing the system libraries/packages that the project depends on
out = run(
    ["apt-get", "update"],
    cwd=DOCKER_MOUNT_POINT,
)

out = run(
    ["apt-get", "build-dep", "-y", name],
    cwd = DOCKER_MOUNT_POINT,
    # stderr=PIPE,
)

out = run(
    [
        "bash",
        "-c",
        # "shopt -s dotglob; cp -ap {}/build {}/{}".format(
        "shopt -s dotglob; mv {}/build {}/{}".format(
            DOCKER_MOUNT_POINT, DOCKER_MOUNT_POINT, basename(json_input["project"]["build"]["temp_build_dir"])
        ),
    ],
    # stdout=subprocess.PIPE,
    # stderr=subprocess.PIPE,
    capture_output=True,
    text=True,
)

ret = run_command("ls -la".split(), cwd=DOCKER_MOUNT_POINT)
print(ret.stdout, flush = True)

if (
    json_input["project"]["build"]["build"] == "success"
    and analyses_to_run != ""
):
    print_section(idx, ctx, "running cxx-langstat for features")

    j = os.environ.get("JOBS", 1)
    cmd = f"cxx-langstat -analyses={analyses_to_run} -emit-features -indir {ast_dir} -outdir {results_dir}/ -j {j} --".split()
    
    analyze_features_start = time()
    ret = run_command(cmd, cwd=DOCKER_MOUNT_POINT, capture_output = True, text = True) #TODO: switch the stdout to None to get the output in the container
    analyze_features_end = time()
    project['size_statistics']['analyze_features_time'] = analyze_features_end - analyze_features_start

    print_section(
        idx, ctx, f"cxx-langstat finished with return code: {ret.returncode}"
    )

    ctx.err_log.print_error(idx, f"cxx-langstat stderr: {ret.stderr}")
    ctx.out_log.print_info(idx, f"cxx-langstat stdout: {ret.stdout}")
    
    print(f"[IDX {idx}] cxx-langstat -emit-features stdout: {ret.stdout}")
    print(f"[IDX {idx}] cxx-langstat -emit-features stderr: {ret.stderr}", flush = True)

    project["features_files"] = {"dir": external_results_dir}
    project["analysis emit-features retcode"] = ret.returncode

    print_section(idx, ctx, "running cxx-langstat for statistics")

    j = os.environ.get("JOBS", 1)
    cmd = f"cxx-langstat -analyses={analyses_to_run} -emit-statistics -indir {results_dir} -out {results_dir}/overall_stats -- {' '.join(ERRORS_TO_OMIT_FLAGS)}".split()

    emit_statistics_start = time()
    ret = run_command(cmd, cwd=DOCKER_MOUNT_POINT, stderr=PIPE)
    emit_statistics_end = time()
    project['size_statistics']['emit_statistics_time'] = emit_statistics_end - emit_statistics_start

    print_section(
        idx, ctx, f"cxx-langstat emit stats finished with return code: {ret.returncode}"
    )

    ctx.err_log.print_error(idx, f"cxx-langstat stderr: {ret.stderr}")
    ctx.out_log.print_info(idx, f"cxx-langstat stdout: {ret.stdout}")
    print(f"[IDX {idx}] cxx-langstat -emit-statistics stdout: {ret.stdout}")
    print(f"[IDX {idx}] cxx-langstat -emit-statistics stderr: {ret.stderr}", flush = True)

    project["features_files"] = {"dir": external_results_dir}
    project["analysis emit-stats retcode"] = ret.returncode

out = {"idx": idx, "name": name, "project": project}
print("output.json content:")
print(json.dumps(out, indent=2), flush = True)

# save output JSON
with open(os.path.join(results_dir, "output.json"), "w") as f:
    json.dump(out, f, indent = 2)


# move logs to build directory
# for file in glob.glob("*.log"):
#     move(file, results_dir)
# copyfile("output.json", os.path.join(results_dir, "output.json"))

print("wrote output.json to disk", flush = True)

# change the user and group to the one of the host, since we are root
for d in set(chown_dirs):
    print("chowning {}...".format(d))
    out = subprocess.run(["chown", "-R", "{}:{}".format(host_uid, host_gid), d])
    if out.returncode != 0:
        print(out)

total_files = 0
# for file in glob.glob(f"**/*.ast.json"):
for file in recursively_get_files(".", ext=".ast.json"):
    total_files += 1
    # os.remove(file)
print(f"Should have {total_files} ast json files", flush = True)