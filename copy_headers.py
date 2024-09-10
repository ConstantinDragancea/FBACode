import os
import os.path
import json
import sys
import shutil

from shutil import copy2, copyfile

def main(project_info):
    if not os.path.exists(project_info):
        print(f"File {project_info} does not exist")
        sys.exit(1)
    
    with open(project_info, 'r') as f:
        project = json.load(f)['project']

    headers_dir = "/root/build/relevant_headers"

    if 'releveant_headers_mapping' in project:
        for header_idx, header_path in project['releveant_headers_mapping'].items():
            # copy2 preserves metadata such as creation and modification times
            # it calls copystat() under the hood
            try:
                if not os.path.exists(os.path.dirname(header_path)):
                    os.makedirs(os.path.dirname(header_path))
                copy2(os.path.join(headers_dir, str(header_idx)), header_path)
            except Exception as e:
                print(f"Failed to copy header {header_idx} to {header_path}. Error: {e}")
    else:
        print("No relevant headers mapping found in project dict")
        print("project object is:")
        print(json.dumps(project, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 copy_headers.py <project_file>")
        sys.exit(1)
    main(sys.argv[1])