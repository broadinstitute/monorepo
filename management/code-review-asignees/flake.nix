{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs_master.url = "github:NixOS/nixpkgs/master";
    systems.url = "github:nix-systems/default";
    devenv.url = "github:cachix/devenv";
  };

  nixConfig = {
    extra-trusted-public-keys = "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw=";
    extra-substituters = "https://devenv.cachix.org";
  };

  outputs = { self, nixpkgs, devenv, systems, ... } @ inputs:
    let
      forEachSystem = nixpkgs.lib.genAttrs (import systems);
    in
    {
      packages = forEachSystem (system: {
        devenv-up = self.devShells.${system}.default.config.procfileScript;
      });

      devShells = forEachSystem
        (system:
          let
            pkgs = import nixpkgs {
              system = system;
              config.allowUnfree = true;
            };


            mpkgs = import inputs.nixpkgs_master {
              system = system;
              config.allowUnfree = true;
            };
          in
          {
            default = devenv.lib.mkShell {
              inherit inputs pkgs;
              modules = [
                {
                  stdenv = pkgs.clangStdenv;
                  env.NIX_LD = nixpkgs.lib.fileContents "${pkgs.stdenv.cc}/nix-support/dynamic-linker";
                  env.NIX_LD_LIBRARY_PATH = nixpkgs.lib.makeLibraryPath (with pkgs; [
                  # Add needed packages here
                  pkgs.stdenv.cc.cc
                  pkgs.libz # for numpy
                  pkgs.libGL
                  pkgs.ruff
                  ]);
                  # https://devenv.sh/reference/options/
                  packages = with pkgs; [
                    mpkgs.poetry
                    python310
                  ];
                  enterShell = ''
                    export LD_LIBRARY_PATH=$NIX_LD_LIBRARY_PATH
                    export CUDA_PATH=${pkgs.cudaPackages.cudatoolkit}
                    export VIRTUAL_ENV=.venv
                    if [ ! -d $VIRTUAL_ENV ]; then
                       export PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring
                       poetry install -vvv --with dev --no-root
                    fi
                    source $VIRTUAL_ENV/bin/activate
                  '';
                }
              ];
            };
          });
    };
}
