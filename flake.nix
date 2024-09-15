{
  description = "Python project with rye template";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = inputs@{ self, ... }:
  with inputs;
  flake-utils.lib.eachDefaultSystem (system:
  let
    pkgs = import nixpkgs { inherit system; overlays = []; };
  in
  {
    devShell = pkgs.mkShell {
      buildInputs = with pkgs; [ rye tcpdump tshark aria2 ];
      shellHook = ''
        rye sync && source .venv/bin/activate
      '';
    };
  });
}
