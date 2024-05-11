find pkgs/ -name '*.nix' -not -name test.nix -not -path '*/test/default.nix' | xargs grep -m1 -H -w -e makeScope -e makeScopeWithSplicing -e recurseIntoAttrs > docs/nixpkgs-scope-files.txt
