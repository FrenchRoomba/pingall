{ lib, buildGoModule, fetchFromGitHub }:
buildGoModule rec {
  pname = "deterministic-zip";
  version = "3.0.1";

  src = fetchFromGitHub {
    owner = "timo-reymann";
    repo = "deterministic-zip";
    rev = "${version}";
    hash = "sha256-zyQ91NoPBgbH4Ob6l3d2RflOpMWJcpo1LNvqHPzhMIw=";
  };

  vendorHash = "sha256-uarCXEeZsNc0qJK9Tukd5esa+3hCB45D3tS9XqkZ4hU=";

  meta = {
    description = "Simple (almost drop-in) replacement for zip that produces deterministic files.";
    homepage = "https://github.com/timo-reymann/deterministic-zip";
    # license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ rhysmdnz ];
  };
}
