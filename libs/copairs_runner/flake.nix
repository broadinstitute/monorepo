{
  description = "2025 Best Practice: Pure uv for Python/PyPI Development on NixOS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python3
            uv
            git
            # System dependencies for binary wheels
            zlib
            stdenv.cc.cc.lib
            # CBC solver for snakemake
            cbc
          ];

          shellHook = ''
            echo "uv Python Development Environment"
            unset PYTHONPATH
            uv sync
          '';

          LD_LIBRARY_PATH = "${pkgs.lib.makeLibraryPath [
            pkgs.zlib
            pkgs.stdenv.cc.cc.lib
          ]}";
        };
      });
}
