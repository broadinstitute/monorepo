{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nixpkgs_master.url = "github:NixOS/nixpkgs/master";
    systems.url = "github:nix-systems/default";
    flake-utils.url = "github:numtide/flake-utils";
    flake-utils.inputs.systems.follows = "systems";
  };

  outputs = { self, nixpkgs, flake-utils, systems, ... } @ inputs:
      flake-utils.lib.eachDefaultSystem (system:
        let
            pkgs = import nixpkgs {
              system = system;
              config.allowUnfree = true;
            };

            mpkgs = import inputs.nixpkgs_master {
              system = system;
              config.allowUnfree = true;
            };

            libList = [
                pkgs.stdenv.cc.cc
              ];
          in
          with pkgs;
        {
          devShells = {
            default  = let
              # These packages get built by Nix, and will be ahead on the PATH
                pwp = (python311.withPackages (p: with p; [
                     python-lsp-server
                     python-lsp-ruff
                   ]));
            in mkShell {
                NIX_LD_LIBRARY_PATH = lib.makeLibraryPath libList;
                packages = [
                  pwp
                  python311Packages.venvShellHook
                  uv
                ]
                ++ libList;
                venvDir = "./.venv";
                postVenvCreation = ''
                    unset SOURCE_DATE_EPOCH
                  '';
                postShellHook = ''
                    unset SOURCE_DATE_EPOCH
                  '';
                shellHook = ''
                    export UV_PYTHON=${pkgs.python311}
                    export LD_LIBRARY_PATH=$NIX_LD_LIBRARY_PATH:$LD_LIBRARY_PATH
                    export PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring

                    runHook venvShellHook
                    uv sync

                    export PYTHONPATH=${pwp}/${pwp.sitePackages}:$PYTHONPATH
                '';
             };
          };
        }
      );
}
