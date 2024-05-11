find pkgs/ -name '*.nix' | xargs du -b | sort -n -r | head -n1000 >docs/nixpkgs-large-nix-files-top1000.txt
