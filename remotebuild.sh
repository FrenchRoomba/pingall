#!/usr/bin/env bash

t=$(mktemp) && (nix path-info --system x86_64-linux --derivation .#gcp.image .#gcp.wrapperImageBuildDir .#azure.archive .#aws.archive .#aws.adapter-archive .#alicloud.archive >$t && xargs <$t nix-copy-closure --to "$1" && ssh <$t "$1" xargs nix-build --keep-going | xargs nix-copy-closure --from "$1")
rm "$t"
