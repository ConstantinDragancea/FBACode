import subprocess
import os
import sys
import shutil
from sys import version_info
from subprocess import CalledProcessError, CompletedProcess
from os import path

def decode(stream):
    if isinstance(stream, bytes) or isinstance(stream, bytearray):
        return stream.decode("utf-8")
    else:
        return stream

def insert_build_stage_markers(rules_file):
    if not os.path.isfile(rules_file):
        print('File not found: ' + rules_file)
        return False
    with open(rules_file, 'r') as f:
        rules = f.readlines()

    # check if override_dh_auto_build* rules exist
    lines_to_override = []
    for i, line in enumerate(rules):
        if line.startswith('override_dh_auto_build'):
            j = i + 1
            while j < len(rules) and rules[j].startswith('\t'):
                j += 1
            lines_to_override.append((i, j))

    if len([x for x in rules if x.startswith('override_dh_auto_build:')]) == 0:
        rules += ['override_dh_auto_build:\n', '\ttouch /tmp/fbacode_build_stage_flag\n', '\tdh_auto_build $@\n', '\trm -f /tmp/fbacode_build_stage_flag\n']

    print(f'Rules to override for file {rules_file}:')
    print(lines_to_override)
    for (line_begin, line_end) in lines_to_override:
        print(rules[line_begin].strip())
        # print(rules[line_begin].strip(), rules[line_end].strip(), sep=' ')

    offset = 0
    for (line_begin, line_end) in lines_to_override:
        rules = rules[:line_begin + offset + 1] + ['\ttouch /tmp/fbacode_build_stage_flag\n'] + rules[line_begin + offset + 1:]
        offset += 1

        rules = rules[:line_end + offset] + ['\trm -f /tmp/fbacode_build_stage_flag\n'] + rules[line_end + offset:]
        offset += 1

    shutil.move(rules_file, f'{rules_file}.bak')
    with open(f'{rules_file}', 'w') as f:
        f.writelines(rules)
    
    return True

def run(command, cwd=None, capture_output = False, text = False, stdout = None, stderr = None) -> CompletedProcess:
    # Python 3.5+ - subprocess.run
    # older - subprocess.call
    # TODO: capture_output added in 3.7 - verify it works
    if version_info.major >= 3 and version_info.minor >= 7:
        out = subprocess.run(command, cwd=cwd, capture_output = capture_output, text = text)
        return CompletedProcess(
            out.args, out.returncode, stdout = decode(out.stdout), stderr = decode(out.stderr)
        )
    else:
        code = 0
        try:
            out = subprocess.check_output(command, cwd=cwd, stderr=subprocess.STDOUT)
        except CalledProcessError as e:
            code = e.returncode
            out = e.output
            return CompletedProcess(command, code, stderr=decode(out))
        return CompletedProcess(command, code, stdout=decode(out))

def recursively_get_files(directory, ext = ""):
    files = []
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(ext):
                files.append(path.join(root, filename))
    return files

def recursively_get_dirs(directory):
    directories = []
    for root, dirs, filenames in os.walk(directory):
        for d in dirs:
            directories.append(path.join(root, d))
    return directories
