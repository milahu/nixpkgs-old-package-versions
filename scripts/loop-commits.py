#!/usr/bin/env python3



import os
import sys
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import argparse
import time
import re
import shlex



debug = 0
#debug = 2



# Constants
NIXPKGS_ORIGIN_URL = "https://github.com/NixOS/nixpkgs"
DEFAULT_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "nixpkgs-old-package-versions")
MAIN_BRANCH = "nixpkgs-unstable"
NIXPKGS_BRANCH_LIST = [MAIN_BRANCH]
NIXPKGS_WORKTREE_MAX_SIZE = 350000000



def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--nixpkgs-repo", help="path to nixpkgs repo")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="cache path")
    args = parser.parse_args()

    if args.cache is None:
        args.cache = DEFAULT_CACHE
        print(f"using default cache {args.cache!r}")

    if args.nixpkgs_repo is None:
        args.nixpkgs_repo = os.path.join(args.cache, "nixpkgs.git")

    # Create or update the nixpkgs repository
    if not os.path.exists(args.nixpkgs_repo):
        print(f"creating nixpkgs repo {args.nixpkgs_repo!r}")
        os.makedirs(args.nixpkgs_repo)
        #cmd = ["git", "clone", "--mirror", NIXPKGS_ORIGIN_URL, args.nixpkgs_repo]
        cmd = ["git", "-C", args.nixpkgs_repo, "init"]
        if debug == 2: print("+", shlex.join(cmd))
        subprocess.run(cmd, check=True)
        cmd = ["git", "-C", args.nixpkgs_repo, "remote", "add", "origin", NIXPKGS_ORIGIN_URL]
        if debug == 2: print("+", shlex.join(cmd))
        subprocess.run(cmd, check=True)
    else:
        fetch_head_path = os.path.join(args.nixpkgs_repo, "FETCH_HEAD") # git fetch
        #fetch_head_path = os.path.join(args.nixpkgs_repo, "HEAD") # git clone --mirror
        last_fetch_time = os.path.getmtime(fetch_head_path)
        last_fetch_date = datetime.fromtimestamp(last_fetch_time, tz=timezone.utc).isoformat()
        print(f"nixpkgs last fetch: {last_fetch_date}")

        nixpkgs_age = int(datetime.now(tz=timezone.utc).timestamp() - last_fetch_time)
        print(f"nixpkgs age: {nixpkgs_age}")

        #if nixpkgs_age > 3600:
        update_max_age = 60*60*24 # 1 day
        if nixpkgs_age > update_max_age:
            cmd = ["git", "-C", args.nixpkgs_repo, "worktree", "list"]
            if debug == 2: print("+", shlex.join(cmd))
            worktree_list = subprocess.run(cmd, check=True, capture_output=True, text=True)
            worktree_list = worktree_list.stdout.strip().split("\n")[1:]
            if worktree_list:
                print("unmounting worktrees")
                for line in worktree_list:
                    worktree_path = line.split()[0]
                    assert os.path.exists(worktree_path)
                    print("unmounting worktree", worktree_path)
                    cmd = ["git", "-C", args.nixpkgs_repo, "worktree", "remove", worktree_path]
                    if debug == 2: print("+", shlex.join(cmd))
                    subprocess.run(cmd, check=True)

            print(f"updating nixpkgs repo {args.nixpkgs_repo!r}")
            t1 = time.time()
            ref_map_list = [f"{b}:{b}" for b in NIXPKGS_BRANCH_LIST]
            cmd = ["git", "-C", args.nixpkgs_repo, "fetch", "origin", *ref_map_list, "--depth=999999999"] # git fetch
            #cmd = ["git", "-C", args.nixpkgs_repo, "remote", "update"] # git clone --mirror
            if debug == 2: print("+", shlex.join(cmd))
            subprocess.run(cmd, check=True)
            t2 = time.time()
            print(f"fetch done in {round(t2 - t1)} sec")
            fetch_head_path = os.path.join(args.nixpkgs_repo, "FETCH_HEAD") # git fetch
            head_path = os.path.join(args.nixpkgs_repo, "HEAD") # git clone --mirror
            with open(fetch_head_path) as f:
                fetch_head_rev = f.read(41)
            assert re.match(r"^[0-9a-f]{40}\t$", fetch_head_rev), f"unexpected fetch_head_rev {repr(fetch_head_rev)}"
            with open(head_path, "w") as f:
                f.write(fetch_head_rev)

    print("mkay")

    # Create a temporary directory for worktrees
    #with tempfile.TemporaryDirectory(prefix="nixpkgs-old-package-versions") as tempdir:
    # tempdir=/run/user/$UID/nixpkgs-old-package-versions
    tempdir = f"/run/user/{os.getuid()}/nixpkgs-old-package-versions"
    os.makedirs(tempdir, exist_ok=True)
    if True:
        tempdir_path = Path(tempdir)
        tempdir_avail = shutil.disk_usage(tempdir_path.parent).free

        if NIXPKGS_WORKTREE_MAX_SIZE > tempdir_avail:
            print("error: tempdir is too small for nixpkgs worktree")
            print(f"tempdir: {tempdir_avail}")
            print(f"nixpkgs: {NIXPKGS_WORKTREE_MAX_SIZE}")
            sys.exit(1)

        # loop branches
        for branch_name in [MAIN_BRANCH]:

            worktree_path = tempdir_path / branch_name
            if worktree_path.exists():
                print(f"re-using worktree path {worktree_path!r}")

                cmd = ["git", "-C", str(worktree_path), "checkout", branch_name]
                if debug == 2: print("+", shlex.join(cmd))
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            else:
                print(f"mounting branch {branch_name!r} on {worktree_path!r}")
                worktree_path.parent.mkdir(parents=True, exist_ok=True)
                #ref = f"remotes/origin/{branch_name}"
                ref = branch_name # mapped branch, aka "remote tracking"
                cmd = ["git", "-C", args.nixpkgs_repo, "worktree", "add", str(worktree_path), ref]
                if debug == 2: print("+", shlex.join(cmd))
                subprocess.run(cmd, check=True)

            # https://stackoverflow.com/questions/1392413
            # Calculating a directory's size using Python

            # mostly useless
            '''
            # 12 seconds
            # this returns the "apparent" size 162956963 (du -sb) (f.stat().st_size)
            # not the "real" size 282161152 (du -s --block-size=1) (f.stat().st_blocks)
            def getsize_recursive(path):
                return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

            # 4.8 seconds
            def get_size_monkut(start_path = '.'):
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(start_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        # skip if it is symbolic link
                        if not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
                return total_size

            # 12 seconds
            def get_size_monkut_2(root_directory):
                return sum(f.stat().st_size for f in root_directory.glob('**/*') if f.is_file())

            # 1.55 sec
            def du_flaschbier(path):
                """disk usage in human readable format (e.g. '2,1GB')"""
                #return subprocess.check_output(['du','-sh', path]).split()[0].decode('utf-8')
                return subprocess.check_output(['du','-s', '--block-size=1', path]).split()[0].decode('utf-8')

            t1 = time.time()
            #worktree_size = getsize_recursive(worktree_path)
            worktree_size = get_size_monkut(worktree_path)
            #worktree_size = get_size_monkut_2(worktree_path)
            #worktree_size = du_flaschbier(worktree_path)
            t2 = time.time()
            print(f"getsize done in {(t2 - t1)} sec")
            print(f"worktree size {worktree_size}")
            '''

            # revision in the current branch
            # most of these revisions are merge commits with 2 parents:
            # the previous commit in this branch
            # the merged commit (can have parents)
            branch_rev = None

            #next_branch_rev = None
            # get next_branch_rev
            cmd = ["git", "-C", str(worktree_path), "rev-parse", branch_name]
            if debug == 2: print("+", shlex.join(cmd))
            rev_parse = subprocess.run(cmd, check=True, capture_output=True, text=True)
            next_branch_rev = rev_parse.stdout.strip()
            if debug == 2: print(f"220 next_branch_rev = {next_branch_rev}")

            # TODO
            # path of commits leading to this merged commit
            #merged_rev_path = []

            # TODO
            # path of multi-parent commits leading to this merged commit
            #merged_rev_nodes = []

            # merged commits of the current branch rev
            #merged_rev_stack = []

            git_log = []
            git_log_idx = None
            git_log_idx_last = None

            # TODO remove?
            head_offset = -1

            # loop commits of this branch
            while True:

                #in_merge = len(merged_rev_stack) > 0
                in_merge = len(git_log) > 0 and git_log_idx < git_log_idx_last

                #print("merged_rev_stack", len(merged_rev_stack), merged_rev_stack)

                # TODO remove?
                if not in_merge:
                    # loop main commits of this branch
                    head_offset += 1

                '''
                if head_offset == 0 and not in_merge:
                    # get next_branch_rev
                    cmd = ["git", "-C", str(worktree_path), "rev-parse", branch_name]
                    if debug == 2: print("+", shlex.join(cmd))
                    rev_parse = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    next_branch_rev = rev_parse.stdout.strip()
                    print(f"220 next_branch_rev = {next_branch_rev}")
                '''

                rev = None

                '''
                if not in_merge:
                    # get next rev on this branch
                    rev = branch_rev = next_branch_rev
                    merged_rev = None
                    merged_rev_path = []
                else:
                    # loop commits of this merge
                    rev = merged_rev = merged_rev_stack[0]
                    merged_rev_stack = merged_rev_stack[1:]
                    #merged_rev_path = [] # TODO
                '''

                if not in_merge:
                    # update git_log
                    rev = branch_rev = next_branch_rev
                    t1 = time.time()
                    '''
                    # subject %s is mostly useless, because most of these commits are merge commits
                    # subject: Merge pull request #309559 from r-ryantm/auto-update/sbt
                    # -> also get %P = parent commits
                    #    to get rev of second parent commit = "merged commit"
                    #    first parent commit = previous commit in this branch
                    # --diff-merges=first-parent # Show full diff with respect to first parent.
                    # no. we need subjects of the merged commits to parse pname and version
                    #cmd = ["git", "-C", str(worktree_path), "show", "--diff-merges=first-parent", "--format=format:%H\n%aI\n%s\n%P\n", "--name-status", f"HEAD~{head_offset}"]
                    #cmd = ["git", "-C", str(worktree_path), "show", "--format=format:%H\n%aI\n%s\n%P\n", "--name-status", rev]
                    '''
                    # https://stackoverflow.com/questions/6191138
                    # How to see commits that were merged in to a merge commit?
                    # git log HEAD^..HEAD --name-status $'--format=format:\n%H\n%aI\n%s\n%P\n'
                    cmd = ["git", "-C", str(worktree_path), "log", "--format=format:\n%H\n%aI\n%s\n%P\n", "--name-status", f"{branch_rev}^..{branch_rev}"]
                    if debug == 2: print("+", shlex.join(cmd))
                    git_log = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.splitlines()
                    git_log_idx = 0
                    git_log_idx_last = len(git_log) - 1
                    #t1 = time.time()
                    t2 = time.time()
                    # 0.07 sec
                    #print(f"git show done in {(t2 - t1)} sec")
                    in_merge = False

                # quickfix. not sure why exactly this is needed...
                if git_log[git_log_idx] == "" and git_log[git_log_idx + 1] == "":
                    git_log_idx += 1

                # "--format=format:\n%H\n%aI\n%s\n%P\n"
                num_fields = 6
                if debug == 2: print("git_log fields", git_log[git_log_idx:(git_log_idx + num_fields)])
                empty1, rev, date, subject, parents, empty2 = git_log[git_log_idx:(git_log_idx + num_fields)]
                git_log_idx += num_fields

                assert empty1 == "", f"empty1: {repr(empty1)}"
                assert empty2 == "", f"empty2: {repr(empty2)}"

                if in_merge:
                    merged_rev = rev
                else:
                    branch_rev = rev
                    merged_rev = None

                parents = parents.split(" ")

                """
                rev = git_log[0]
                date = git_log[1]
                subject = git_log[2]
                """

                subject_pr = re.match(r"^Merge pull request #([0-9]+) from [^ ]+/[^ ]+$", subject)
                if subject_pr:
                    subject_pr = subject_pr.group(1)

                # first parent commit
                # = previous commit in this branch
                # = next commit in the loop
                assert len(parents) <= 2 # TODO can a git commit have more than two parents
                #if not in_merge:
                #    next_branch_rev = parents[0]
                next_branch_rev = parents[0]
                #merged_rev = parents[1] if len(parents) > 1 else None
                # separator before name-status lines
                #assert git_log[4] == ""

                if len(parents) > 1:
                    # no name-status lines
                    # next line is rev of first merged commit == parents[1]
                    assert git_log[git_log_idx] == ""

                # populate stack? - no, not here

                ############

                indent = "  " if in_merge else ""

                #print(indent + f"rev: {rev}")
                if merged_rev:
                    print(indent + f"rev: {merged_rev}")
                else:
                    print(indent + f"rev: {branch_rev}")
                print(indent + f"  date: {date}")
                print(indent + f"  subject: {subject}")
                print(indent + f"  parents: {parents}")

                ############

                if debug == 2 and not in_merge:
                    print(indent + f"  270 next_branch_rev = {next_branch_rev}")

                '''
                if in_merge and parents:
                    # add first parent to stack
                    print(f"merged_rev_stack.append(parents[0]={repr(parents[0])})")
                    merged_rev_stack.append(parents[0])
                '''

                """
                if merged_rev:
                    # if in merge, add other parents to stack
                    print(f"merged_rev_stack.append(merged_rev={repr(merged_rev)})")
                    merged_rev_stack.append(merged_rev)
                    '''
                    # get subject of the merged commit
                    cmd = ["git", "-C", str(worktree_path), "show", "--diff-merges=first-parent", "--format=format:%H\n%aI\n%s\n%P\n", "--name-status", merged_rev]
                    if debug == 2: print(indent + "+", shlex.join(cmd))
                    show_output = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    lines2 = show_output.stdout.splitlines()
                    '''
                """

                #for line in git_log[5:]:
                #while git_log[git_log_idx] != "" and git_log_idx <= git_log_idx_last:
                if debug == 2: print(f"looping git log from {git_log_idx}:", git_log[git_log_idx:])
                git_log_idx -= 1
                while True:
                    git_log_idx += 1
                    if git_log_idx > git_log_idx_last:
                        break
                    if git_log[git_log_idx] == "":
                        #git_log_idx += 1 # no
                        break
                    line = git_log[git_log_idx]
                    status, path = line.split("\t", 1)
                    #print(indent + f"status: {status} -- path: {path}") # debug
                    print(indent + f"  path: {path}") # debug
                    # status: M
                    #print(indent + f"    status: {status}")
                    # M = modified = update package
                    # A = added = init package
                    if status not in ("M", "A"):
                        # TODO implement status R092 of path pkgs/applications/misc/flowtime/default.nix  pkgs/by-name/fl/flowtime/package.nix
                        print(indent + f"    TODO implement status {status} of path {path}")
                        continue

                    if path.startswith("pkgs/top-level/"):
                        # TODO parse attribute of package. can be different than pname
                        # pkgs/top-level/all-packages.nix
                        # pkgs/top-level/python-packages.nix
                        print(indent + f"    TODO implement diff {path}")
                        continue

                    if path.startswith("pkgs/development/node-packages/"):
                        # pkgs/development/node-packages/node-packages.nix is generated by
                        # pkgs/development/node-packages/generate.sh from
                        # pkgs/development/node-packages/node-packages.json
                        print(indent + f"    TODO implement diff {path}")
                        continue

                    if path == "pkgs/applications/editors/vim/plugins/generated.nix":
                        print(indent + f"    TODO implement diff {path}")
                        continue

                    if path == "pkgs/applications/editors/vscode/extensions/default.nix":
                        print(indent + f"    TODO implement diff {path}")
                        continue

                    if not path.startswith("pkgs/"):
                        print(indent + "    ignoring")
                        continue

                    t1 = time.time()
                    #cmd = ["git", "-C", str(worktree_path), "diff", "-U999999", f"HEAD~{head_offset + 1}", f"HEAD~{head_offset}", "--", path]
                    cmd = ["git", "-C", str(worktree_path), "diff", "-U999999", rev + "^", rev, "--", path]
                    if debug == 2: print(indent + "+", shlex.join(cmd))
                    diff_output = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    #t1 = time.time()
                    t2 = time.time()
                    # 0.05 sec
                    #print(indent + f"git diff done in {(t2 - t1)} sec")

                    file_diff = diff_output.stdout.splitlines()
                    # TODO pname regex?
                    #file_diff = [line for line in diff_output.stdout.splitlines() if ' pname = "' in line or ' version = "' in line]
                    #           grep -E -e ' pname = "[a-z_-]+";' -e ' version = "[a-zA-Z0-9._+@-]+";'
                    #file_diff = [line for line in diff_output.stdout.splitlines() if re.search(r'\bpname = "[a-z_-]+";$|\bversion = "[a-zA-Z0-9._+@-]+";$', line)]

                    #print(indent + f"diff {path}")
                    #print(indent + "\n".join(["  " + line for line in file_diff]))

                    #print(indent + "file_diff", file_diff)

                    #pname_lines = [line for line in file_diff if 'pname = "' in line]
                    pname_lines = [line for line in file_diff if re.search(r'\bpname = "[a-z_-]+";$', line)]

                    #print(indent + "pname_lines", pname_lines)

                    '''
                    pname_n = len(pname_lines)
                    if pname_n != 1 and pname_n != 2:
                        print(indent + f"error: pname_n {pname_n} in path {path!r}")
                        continue
                    '''

                    # TODO parse pname and version from subject
                    # subject can be
                    # lmstudio: 0.2.18 -> 0.2.20
                    # python311Packages.rapidgzip: 0.13.2 -> 0.13.3 (#308099)
                    # libgedit-tepl: 6.8.0 → 6.10.0, renamed from tepl
                    # python311Packages.pygame-gui: switch to pygame-ce
                    # firmware-updater: unstable-2023-09-17 -> unstable-2024-18-04 (#308100)
                    # libsForQt5.qtpurchasing: init
                    # home-assistant-custom-component.ntfy: init at 1.0.2

                    pname_0 = [line for line in pname_lines if line.startswith(" ")]
                    pname_a = [line for line in pname_lines if line.startswith("-")]
                    pname_b = [line for line in pname_lines if line.startswith("+")]
                    #print(indent + f"pname: 0:{pname_0} a:{pname_a} b:{pname_b}")
                    if not pname_0 and not pname_a and not pname_b:
                        pname = None
                    elif len(pname_0) == 1 and not pname_a and not pname_b:
                        # const pname
                        pname = pname_0[0].split('"')[1]
                        print(indent + f"    pname: {pname}")
                        # TODO compare to subject
                    elif not pname_0 and len(pname_a) == 1 and len(pname_b) == 1:
                        # diff pname
                        pname = (
                            pname_a[0].split('"')[1],
                            pname_b[0].split('"')[1],
                        )
                        print(indent + f"    pname: {pname[0]} -> {pname[1]}")
                        # TODO compare to subject
                    elif status == "A" and not pname_0 and not pname_a and len(pname_b) == 1:
                        # init pname
                        pname = pname_b[0].split('"')[1]
                    else:
                        # pkgs/servers/home-assistant/default.nix
                        print(indent + f"    TODO unexpected pname matches in {path}")
                        print(indent + "\n".join(["      " + line for line in (pname_lines)]))
                        continue

                    #version_lines = [line for line in file_diff if 'version = "' in line]
                    version_lines = [line for line in file_diff if re.search(r'\bversion = "[a-zA-Z0-9._+@-]+";$', line)]

                    '''
                    version_n = len(version_lines)
                    if version_n != 1 and version_n != 2:
                        print(indent + f"error: version_n {version_n} in path {path!r}")
                        continue
                    '''

                    version_0 = [line for line in version_lines if line.startswith(" ")]
                    version_a = [line for line in version_lines if line.startswith("-")]
                    version_b = [line for line in version_lines if line.startswith("+")]
                    #print(indent + f"version: 0:{version_0} a:{version_a} b:{version_b}")
                    if not version_0 and not version_a and not version_b:
                        version = None
                    elif len(version_0) == 1 and not version_a and not version_b:
                        # const version
                        version = version_0[0].split('"')[1]
                        print(indent + f"    version: {version}")
                        # TODO compare to subject
                    elif not version_0 and len(version_a) == 1 and len(version_b) == 1:
                        # diff version
                        version = (
                            version_a[0].split('"')[1],
                            version_b[0].split('"')[1],
                        )
                        print(indent + f"    version: {version[0]} -> {version[1]}")
                        # TODO compare to subject
                    elif status == "A" and not version_0 and not version_a and len(version_b) == 1:
                        # init version
                        version = version_b[0].split('"')[1]
                    else:
                        print(indent + f"    TODO unexpected version matches in {path}")
                        # pkgs/applications/editors/jupyter-kernels/iruby/gemset.nix -> ignore
                        print(indent + "\n".join(["      " + line for line in (version_lines)]))
                        continue

                    if not pname and not version:
                        print(indent + "    no pname, no version")
                    elif pname and not version:
                        print(indent + "    TODO only pname was found")
                    elif not pname and version:
                        print(indent + "    TODO only version was found")

                    #print(indent + f"path {path} -- pname {pname} -- version {version}")



if __name__ == "__main__":
    main()
