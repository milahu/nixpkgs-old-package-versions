## git clone nixpkgs

### bare

initial fetch takes 80 minutes for 4 GB

```
$ git init
$ git remote add origin https://github.com/NixOS/nixpkgs
$ time git fetch origin nixpkgs-unstable
remote: Enumerating objects: 4876034, done.
remote: Counting objects: 100% (4600194/4600194), done.
remote: Compressing objects: 100% (1107608/1107608), done.
remote: Total 4568535 (delta 3177162), reused 4544399 (delta 3155701), pack-reused 0
Receiving objects: 100% (4568535/4568535), 3.57 GiB | 6.98 MiB/s, done.
Resolving deltas: 100% (3177162/3177162), completed with 7424 local objects.
```

### mirror

is "git clone --mirror" faster than "git clone"?

initial mirror-clone takes 70 minutes for 5 GB

but update takes much longer, because there are thousands of useless refs (github pull requests)

```
$ time git clone --mirror https://github.com/NixOS/nixpkgs nixpkgs.git
Cloning into bare repository 'nixpkgs.git'...
remote: Enumerating objects: 6644945, done.
remote: Counting objects: 100% (8522/8522), done.
remote: Compressing objects: 100% (4285/4285), done.
remote: Total 6644945 (delta 6559), reused 5705 (delta 4046), pack-reused 6636423
Receiving objects: 100% (6644945/6644945), 4.91 GiB | 5.88 MiB/s, done.
Resolving deltas: 100% (4501561/4501561), done.
Checking objects: 100% (16777216/16777216), done.

real    66m37.297s
user    116m13.509s
sys     10m46.224s
```
