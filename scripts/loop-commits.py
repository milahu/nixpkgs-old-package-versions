#!/usr/bin/env python3

# https://codingfleet.com/code-converter/bash/python/

import os
import sys
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Constants
NIXPKGS_ORIGIN_URL = 'https://github.com/NixOS/nixpkgs'
DEFAULT_CACHE_PATH = os.path.join(os.path.expanduser('~'), '.cache', 'nixpkgs-old-package-versions')
MAIN_BRANCH = 'nixpkgs-unstable'
NIXPKGS_BRANCH_LIST = [MAIN_BRANCH]
NIXPKGS_WORKTREE_MAX_SIZE = 350000000

# Parse arguments
nixpkgs_repo_path = None
cache_path = None

for arg in sys.argv[1:]:
    if arg == '--nixpkgs-repo':
        nixpkgs_repo_path = sys.argv[sys.argv.index(arg) + 1]
    elif arg == '--cache':
        cache_path = sys.argv[sys.argv.index(arg) + 1]
    else:
        print(f"error: unrecognized argument {arg!r}")
        sys.exit(1)

if cache_path is None:
    cache_path = DEFAULT_CACHE_PATH
    print(f"using default cache {cache_path!r}")

if nixpkgs_repo_path is None:
    nixpkgs_repo_path = os.path.join(cache_path, 'nixpkgs.git')

# Create or update the nixpkgs repository
if not os.path.exists(nixpkgs_repo_path):
    print(f"creating nixpkgs repo {nixpkgs_repo_path!r}")
    subprocess.run(['git', 'clone', '--mirror', NIXPKGS_ORIGIN_URL, nixpkgs_repo_path], check=True)
else:
    fetch_head_path = os.path.join(nixpkgs_repo_path, 'FETCH_HEAD')
    last_fetch_time = os.path.getmtime(fetch_head_path)
    last_fetch_date = datetime.fromtimestamp(last_fetch_time, tz=timezone.utc).isoformat()
    print(f"nixpkgs last fetch: {last_fetch_date}")

    nixpkgs_age = int(datetime.now(tz=timezone.utc).timestamp() - last_fetch_time)
    print(f"nixpkgs age: {nixpkgs_age}")

    if nixpkgs_age > 3600:
        print(f"updating nixpkgs repo {nixpkgs_repo_path!r}")
        fetch_refs = ' '.join(NIXPKGS_BRANCH_LIST)
        subprocess.run(['git', '-C', nixpkgs_repo_path, 'fetch', 'origin', fetch_refs, '--depth=999999999'], check=True)

print("mkay")

# Create a temporary directory for worktrees
with tempfile.TemporaryDirectory(prefix='nixpkgs-old-package-versions') as tempdir:
    tempdir_path = Path(tempdir)
    tempdir_avail = shutil.disk_usage(tempdir_path.parent).free

    if NIXPKGS_WORKTREE_MAX_SIZE > tempdir_avail:
        print("error: tempdir is too small for nixpkgs worktree")
        print(f"tempdir: {tempdir_avail}")
        print(f"nixpkgs: {NIXPKGS_WORKTREE_MAX_SIZE}")
        sys.exit(1)

    for branch in [MAIN_BRANCH]:
        worktree_path = tempdir_path / branch
        if worktree_path.exists():
            print(f"re-using worktree path {worktree_path!r}")
        else:
            print(f"mounting branch {branch!r} on {worktree_path!r}")
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
            ref = f"remotes/origin/{branch}"
            subprocess.run(['git', '-C', nixpkgs_repo_path, 'worktree', 'add', str(worktree_path), ref], check=True)

        worktree_size = sum(f.stat().st_size for f in worktree_path.glob('**/*') if f.is_file())
        print(f"worktree size {worktree_size}")

        show_output = subprocess.run(['git', '-C', str(worktree_path), 'show', '--first-parent', '--format=format:%H\n%aI', '--name-status', 'HEAD'], check=True, capture_output=True, text=True)
        lines = show_output.stdout.splitlines()
        rev = lines[0]
        date = lines[1]
        print(f"rev: {rev}")
        print(f"date: {date}")

        for line in lines[2:]:
            status, path = line.split('\t', 1)
            print(f"status: {status} -- path: {path}")
            if status != 'M':
                continue

            if path.startswith('pkgs/top-level/'):
                continue

            diff_output = subprocess.run(['git', '-C', str(worktree_path), 'diff', '-U999999', 'HEAD^', 'HEAD', '--', path], check=True, capture_output=True, text=True)
            file_diff = '\n'.join(line for line in diff_output.stdout.splitlines() if ' pname = "' in line or ' version = "' in line)
            print(f"diff {path}")
            print('\n'.join(['  ' + line for line in file_diff.splitlines()]))

            pname_lines = [line for line in file_diff.splitlines() if ' pname = "' in line]
            pname_n = len(pname_lines)
            if pname_n != 1 and pname_n != 2:
                print(f"error: pname_n {pname_n} in path {path!r}")
                continue

            pname_0 = next((line for line in pname_lines if line.startswith(' ')), None)
            pname_a = next((line for line in pname_lines if line.startswith('-')), None)
            pname_b = next((line for line in pname_lines if line.startswith('+')), None)
            print(f"pname: 0:{pname_0} a:{pname_a} b:{pname_b}")

            version_lines = [line for line in file_diff.splitlines() if ' version = "' in line]
            version_n = len(version_lines)
            if version_n != 1 and version_n != 2:
                print(f"error: version_n {version_n} in path {path!r}")
                continue

            version_0 = next((line for line in version_lines if line.startswith(' ')), None)
            version_a = next((line for line in version_lines if line.startswith('-')), None)
            version_b = next((line for line in version_lines if line.startswith('+')), None)
            print(f"version: 0:{version_0} a:{version_a} b:{version_b}")
