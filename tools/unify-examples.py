import json
import os

from os.path import exists

SOURCE_FILENAMES = [
    "./examples/debian-success-test.json",
    "./examples/debian-success-test-50.json",
    "./examples/debian-success-test-100.json",
    "./examples/debian-success-test-200.json",
    "./examples/debian-success-test-400.json",
    "./examples/debian-success-test-500.json",
    "./examples/debian-success-test-700.json",
    "./examples/debian-success-test-800.json",
    "./examples/debian-success-test-1600.json",
]

def main():
    built_projects = dict()
    output_object = { "debian": {} }

    # load built projects
    if exists("./all_built.json"):
        with open("./all_built.json", "r") as f:
            temp_data = json.load(f)
        built_projects.update(temp_data)
        print(f"Loaded all_built projects")
    
    if exists("./intermediate_all_built.json"):
        with open("./intermediate_all_built.json", "r") as f:
            temp_data = json.load(f)
        built_projects.update(temp_data)
        print(f"Loaded intermediate_all_built projects")
    
    for file in SOURCE_FILENAMES:
        if not exists(file):
            continue
        with open(file, "r") as f:
            data = json.load(f)
            data = data["debian"]

        for project in data:
            if project in built_projects:
                continue
            output_object["debian"][project] = data[project]
            # print(f"Loaded project {project}")
    
    print(len(output_object["debian"]))
    with open("./examples/debian-success-test-unified.json", "w") as f:
        json.dump(output_object, f, indent=2)

if __name__ == "__main__":
    main()