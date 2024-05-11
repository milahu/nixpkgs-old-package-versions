# nixpkgs-package-version-log

map package versions to nixpkgs revisions

alternative implementation of [lazamar/nix-package-versions](https://github.com/lazamar/nix-package-versions)

upstream issue:
[Use git log instead of downloading xy tar archives](https://github.com/lazamar/nix-package-versions/issues/29)



## status

early draft



## goals



### reduce network traffic

dont fetch full tarball of every nixpkgs revision

use a deep clone of the nixpkgs repo



### reduce cpu time

avoid nix eval via `nix-env -q`

parse package updates from output of `git log` and `git diff`



### produce static html files

static files can be hosted on github pages

use package attribute as path, for example `python3Packages/requests.html`
