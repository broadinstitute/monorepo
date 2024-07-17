{
  inputs = {
    dream2nix.url = "github:nix-community/dream2nix";
    nixpkgs.follows = "dream2nix/nixpkgs";
    nixpkgs_master.url = "github:NixOS/nixpkgs/master";
    flake-utils.url = "github:numtide/flake-utils";
    systems.url = "github:nix-systems/default";
    devenv.url = "github:cachix/devenv";
  };

  outputs = { self, nixpkgs, devenv, systems, dream2nix, ... } @ inputs:
    inputs.flake-utils.lib.eachDefaultSystem (system:
      let

        pkgs = import nixpkgs {
          system = system;
          config.allowUnfree = true;
        };

        mpkgs = import inputs.nixpkgs_master {
          system = system;
          config.allowUnfree = true;
        };

      in rec {
        apps = rec{
          ipstack = {
            type = "app";
            program = "${packages.default}/bin/ipstack";
          };
          default = ipstack;
        };
        packages = rec {
          ipstack = dream2nix.lib.evalModules {
            packageSets.nixpkgs = pkgs;
            modules = [
              ./nix/default.nix
              {
                paths.projectRoot = ./.;
                paths.projectRootFile = "flake.nix";
                paths.package = ./.;
              }
            ];
          };
          default = ipstack;
        };

        devShells =
          let
            python_with_pkgs = (pkgs.python310.withPackages(pp: []));
          in
            with pkgs;
            {
              default = pkgs.mkShell {
                NIX_LD = runCommand "ld.so" {} ''
                  ln -s "$(cat '${pkgs.stdenv.cc}/nix-support/dynamic-linker')" $out
                '';
                NIX_LD_LIBRARY_PATH = lib.makeLibraryPath [
                  pkgs.zlib
                ];
                packages = [
                  rye
                ];
                venvDir = "./.venv";
                postVenvCreation = ''
                  unset SOURCE_DATE_EPOCH
                '';
                postShellHook = ''
                  unset SOURCE_DATE_EPOCH
                '';
                shellHook = ''
                  export LD_LIBRARY_PATH=$NIX_LD_LIBRARY_PATH
                  export PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring
                  runHook venvShellHook
                  export PYTHONPATH=${python_with_pkgs}/${python_with_pkgs.sitePackages}:$PYTHONPATH
                  rye sync
              '';
              };
            };
      }
    );
}
