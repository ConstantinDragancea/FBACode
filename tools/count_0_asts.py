import json
import os

def main():
    with open("all_built.json", "r") as f:
        all_built = json.load(f)

    no_asts = 0
    for project_name, project in all_built.items():
        if project["status"] != "success":
            continue
        if project["ast_files"]["files"] == 0:
            no_asts += 1
    
    print(f"Projects with no AST files: {no_asts}")

    with open("./tools/remote_build_summary.json", "r") as fin:
        remote_built = json.load(fin)

    success_projects_local = [pname for (pname, project) in all_built.items() if project["status"] == "success"]
    success_projects_remote = [pname for (pname, project) in remote_built.items() if project["status"] == "success"]

    success_projects_local = set(success_projects_local)
    success_projects_remote = set(success_projects_remote)

    print(f"Nr of successful projects that are not on the remote: {len(success_projects_local - success_projects_remote)}")
    print(f"Nr of successful projects that are not local: {len(success_projects_remote - success_projects_local)}")

    # for project_name, project in all_built.items():
    #     if project["status"] != "success":
    #         continue
    #     success_projects_local[project_name] = project

if __name__ == "__main__":
    main()