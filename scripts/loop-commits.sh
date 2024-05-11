#!/usr/bin/env bash

#set -e
set -u
#set -x # debug

# can be normal or bare repo
nixpkgs_repo_path=
cache_path=
nixpkgs_origin_url='https://github.com/NixOS/nixpkgs'

default_cache_path="$HOME/.cache/nixpkgs-old-package-versions"

# parse args
while [ $# != 0 ]; do case "$1" in
  --nixpkgs-repo) nixpkgs_repo_path="$2"; shift 2; continue ;;
  --cache) cache_path="$2"; shift 2; continue;;
  *) echo "error: unrecognized argument ${1@Q}"; exit 1;;
esac; done

if [ -z "$cache_path" ]; then
  cache_path="$default_cache_path"
  echo "using default cache ${cache_path@Q}"
fi

main_branch=nixpkgs-unstable

nixpkgs_branch_list=(
  $main_branch
  # TODO more?
)

if [ -n "$nixpkgs_repo_path" ]; then
  echo "using nixpkgs repo ${nixpkgs_repo_path@Q}"
else
  nixpkgs_repo_path="$cache_path/nixpkgs.git"
fi

if ! [ -e "$nixpkgs_repo_path" ]; then
  echo "creating nixpkgs repo ${nixpkgs_repo_path@Q}"
  if false; then
    mkdir -p "$nixpkgs_repo_path"
    git -C "$nixpkgs_repo_path" init --bare
    git -C "$nixpkgs_repo_path" remote add origin "$nixpkgs_origin_url"
  else
    echo + git clone --mirror "$nixpkgs_origin_url" "$nixpkgs_repo_path"
    time \
    git clone --mirror "$nixpkgs_origin_url" "$nixpkgs_repo_path"
  fi
fi

# TODO why main? why not master?
# $ cat /home/user/.cache/nixpkgs-old-package-versions/nixpkgs.git/HEAD
# ref: refs/heads/main

#read last_commit_time last_commit_date < <(git -C "$nixpkgs_repo_path" show remotes/origin/$main_branch --format="%at %aI")

read last_fetch_time last_fetch_date < <(stat -c"%Y %y" "$nixpkgs_repo_path/FETCH_HEAD")
#last_fetch_time=$(stat -c%Y "$nixpkgs_repo_path/FETCH_HEAD")
#last_fetch_date=$(stat -c%y "$nixpkgs_repo_path/FETCH_HEAD")

#echo "nixpkgs last fetch: $last_fetch_time"
echo "nixpkgs last fetch: $last_fetch_date"

nixpkgs_age=$(($(date +%s) - $last_fetch_time))
echo "nixpkgs age: $nixpkgs_age"

# TODO? dont use version? reuse tempdir from previous run?
#version=$(date --utc +%Y%m%dT%H%M%SZ).$(mktemp -u XXXXXXXX)

# use tmpfs to avoid disk writes
#tempdir=/run/user/$UID/nixpkgs-old-package-versions.$version
tempdir=/run/user/$UID/nixpkgs-old-package-versions

tempdir_avail=$(df --block-size=1 --output=avail /run/user/$UID | tail -n+2)

#nixpkgs_worktree_max_size=282161152 # 2024-05-09
nixpkgs_worktree_max_size=350000000

if ((nixpkgs_worktree_max_size > tempdir_avail)); then
  echo "error: tempdir is too small for nixpkgs worktree"
  echo "tempdir: $tempdir_avail"
  echo "nixpkgs: $nixpkgs_worktree_max_size"
  exit 1
fi

# TODO check free disk space on tmpfs
# df -h /run/user/1000

if ((nixpkgs_age > 3600)); then
  echo "updating nixpkgs repo ${nixpkgs_repo_path@Q}"
  fetch_refs=""
  for branch in ${nixpkgs_branch_list[@]}; do
    #fetch_refs+=" $branch:$branch"
    fetch_refs+=" $branch"
  done
  time \
  git -C "$nixpkgs_repo_path" fetch origin $fetch_refs --depth=999999999
fi

echo mkay

for branch in $main_branch; do
  worktree_path="$tempdir/$branch"

  if [ -e "$worktree_path" ]; then
    echo "re-using worktree path ${worktree_path@Q}"
  else
    echo "mounting branch ${branch@Q} on ${worktree_path@Q}"
    mkdir -p "${worktree_path%/*}"
    ref="remotes/origin/$branch"
    time \
    git -C "$nixpkgs_repo_path" worktree add "$worktree_path" "$ref"
  fi

  worktree_size=$(du --block-size=1 --summarize "$worktree_path" | cut -d$'\t' -f1)
  echo "worktree size $worktree_size"

  {
    read rev
    echo "rev: $rev"
    read date
    echo "date: $date"
    #set -x # debug
    while read line; do
      #echo "line: ${line@Q}"
      # fixed by removing "set -e"
      # TODO why does read return nonzero
      #{ read -d'\t' status path || true; } <<<"$line"
      read -d'\t' status path <<<"$line"
      echo "status: $status -- path: $path"
      if [ "$status" != "M" ]; then
        : # TODO
      fi
      # status M = modified
      if [[ "$path" == "pkgs/top-level/"* ]]; then
        :
        # TODO
      else
        file_diff=$(
          set -x
          git -C "$worktree_path" diff -U999999 HEAD^ HEAD -- "$path" |
          grep -E -e ' pname = "[a-z_-]+";' -e ' version = "[a-zA-Z0-9._+@-]+";'
          #grep -E -e '^[+-]' -e ' pname = "[a-z_-]+"' -e ' version = "[a-zA-Z0-9_+@-]+"'
          #grep -E -e '^[+- ]  pname = "' -e '^[+- ]  version = "'
        )
        echo "diff $path"
        echo "$file_diff" | sed 's/^/  /'

        pname_n=$(echo "$file_diff" | grep '\bpname = "' | wc -l)
        if [ $pname_n != 1 ] && [ $pname_n != 2 ]; then
          echo "error: pname_n $pname_n in path ${path@Q}"
          continue
        fi
        pname_0=$(echo "$file_diff" | grep -E '^[ ].*\bpname = "')
        pname_a=$(echo "$file_diff" | grep -E '^[-].*\bpname = "')
        pname_b=$(echo "$file_diff" | grep -E '^[+].*\bpname = "')
        echo "pname: 0:$pname_0 a:$pname_a b:$pname_b"

        version_n=$(echo "$file_diff" | grep '\bversion = "' | wc -l)
        if [ $version_n != 1 ] && [ $version_n != 2 ]; then
          echo "error: version_n $version_n in path ${path@Q}"
          continue
        fi
        version_0=$(echo "$file_diff" | grep -E '^[ ].*\bversion = "')
        version_a=$(echo "$file_diff" | grep -E '^[-].*\bversion = "')
        version_b=$(echo "$file_diff" | grep -E '^[+].*\bversion = "')
        echo "version: 0:$version_0 a:$version_a b:$version_b"
      fi
    done
  } < <(
    set -x
    git -C "$worktree_path" show --first-parent --format=format:$'%H\n%aI' --name-status HEAD
  )
  # ad7efee13e0d216bf29992311536fce1d3eefbef
  # 2024-05-07T01:18:04+02:00
  # M       pkgs/development/python-modules/django/5.nix

done
