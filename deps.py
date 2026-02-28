#!/usr/bin/env python3
import os
import subprocess
import pulumi

depNames = [
    "azure.archive",
    "gcp.image",
    "aws.archive",
    "aws.adapter-archive",
    "alicloud.archive",
]

pulumi.info("Loading nix dependencies...")

nix_env = os.environ.copy()
nix_env["NIXPKGS_ALLOW_UNFREE"] = "1"

drvs = (
    subprocess.run(
        [
            "nix",
            "build",
            "--impure",
            "--print-out-paths",
            "--system",
            "x86_64-linux",
        ]
        + sum(
            ([f"{os.path.dirname(os.path.realpath(__file__))}#{x}"] for x in depNames),
            [],
        ),
        env=nix_env,
        check=True,
        stdout=subprocess.PIPE,
    )
    .stdout.decode()
    .split("\n")
)

nixdeps = {name: drv.strip() for name, drv in zip(depNames, drvs)}

pulumi.info("Dependencies loaded.")
