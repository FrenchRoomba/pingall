{
  lib,
  pkgsStatic,
  naersk,
  nix-gitignore,
  cloud ? null,
}:
# ((mkRustPackageOrWorkspace { src = (nix-gitignore.gitignoreSource [ ] ../app); }).release.pinger.override { features = lib.optional (cloud != null) cloud; }).bin
naersk.buildPackage {
  src = (nix-gitignore.gitignoreSource [ ] ../app);

  cargoBuildOptions = x: x ++ [ "--features ${cloud}" ];

  # Tells Cargo that we're building for musl.
  # (https://doc.rust-lang.org/cargo/reference/config.html#buildtarget)
  CARGO_BUILD_TARGET = "x86_64-unknown-linux-musl";
  CARGO_TARGET_X86_64_UNKNOWN_LINUX_MUSL_LINKER = "${pkgsStatic.stdenv.cc}/bin/${pkgsStatic.stdenv.cc.targetPrefix}cc";
  CC_x86_64_unknown_linux_musl = "${pkgsStatic.stdenv.cc}/bin/${pkgsStatic.stdenv.cc.targetPrefix}cc";
  CXX_x86_64_unknown_linux_musl = "${pkgsStatic.stdenv.cc}/bin/${pkgsStatic.stdenv.cc.targetPrefix}c++";

  # Tells Cargo to enable static compilation.
  # (https://doc.rust-lang.org/cargo/reference/config.html#buildrustflags)
  #
  # Note that the resulting binary might still be considered dynamically
  # linked by ldd, but that's just because the binary might have
  # position-independent-execution enabled.
  # (see: https://github.com/rust-lang/rust/issues/79624#issuecomment-737415388)
  CARGO_BUILD_RUSTFLAGS = "-C target-feature=+crt-static";
}
