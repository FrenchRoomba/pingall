{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    naersk.url = "github:nix-community/naersk";
    naersk.inputs.nixpkgs.follows = "nixpkgs";
    fenix.url = "github:nix-community/fenix";
    fenix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, naersk, fenix, ... }@inputs:
    let
      pkgs = (import nixpkgs) {
        system = "x86_64-linux";
      };
      toolchain = with fenix.packages.x86_64-linux;
        combine [
          minimal.rustc
          minimal.cargo
          targets.x86_64-unknown-linux-musl.latest.rust-std
        ];
      naersk' = pkgs.callPackage naersk {
        cargo = toolchain;
        rustc = toolchain;
      };
    in
    rec{
      packages.x86_64-linux = {
        gcp = rec {
          pinger = pkgs.callPackage nix/pinger.nix { cloud = "gcp"; naersk = naersk'; };
          image = pkgs.callPackage nix/image.nix { name = "memes.nz/pinger-gcp"; inherit pinger; };
        };

        aws = rec {
          pinger = pkgs.callPackage nix/pinger.nix { cloud = "aws"; naersk = naersk'; };
          archive = pkgs.runCommandLocal "aws-pinger-archive.zip" { } ''
            mkdir build
            cd build
            cp ${pinger}/bin/pinger ./bootstrap

            ${pkgs.zip}/bin/zip -r $out *
          '';
        };

        alicloud = rec {
          pinger = pkgs.callPackage nix/pinger.nix { cloud = "alicloud"; naersk = naersk'; };
          archive = pkgs.runCommandLocal "alicloud-pinger-archive.zip" { } ''
            mkdir build
            cd build
            cp ${pinger}/bin/pinger ./bootstrap

            ${pkgs.zip}/bin/zip -r $out *
          '';
        };

        azure = rec {
          pinger = pkgs.callPackage nix/pinger.nix { cloud = "azure"; naersk = naersk'; };

          functionJson = pkgs.writeText "function.json" (builtins.toJSON {
            bindings = [
              {
                authLevel = "anonymous";
                type = "httpTrigger";
                direction = "in";
                name = "req";
              }
              {
                type = "http";
                direction = "out";
                name = "res";
              }
            ];
          });

          hostJson = pkgs.writeText "host.json" (builtins.toJSON {
            version = "2.0";
            logging = {
              logLevel = {
                default = "Trace";
              };
              applicationInsights = {
                samplingSettings = {
                  isEnabled = true;
                  excludedTypes = "Request";
                };
              };
            };
            extensionBundle = {
              id = "Microsoft.Azure.Functions.ExtensionBundle";
              version = "[4.0.0, 5.0.0)";
            };
            customHandler = {
              description = {
                defaultExecutablePath = "pinger/pinger";
                workingDirectory = "";
                arguments = [ ];
              };
              enableForwardingHttpRequest = true;
            };
          });

          archive = pkgs.runCommandLocal "azure-pinger-archive.zip" { } ''
            mkdir build
            cd build
            cp ${hostJson} host.json
            mkdir pinger
            cp ${functionJson} pinger/function.json

            cp ${pinger}/bin/pinger ./pinger/pinger

            ${pkgs.zip}/bin/zip -r $out *
          '';
        };
      };
    };

}
