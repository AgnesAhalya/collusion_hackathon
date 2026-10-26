"""Decrypt a downloaded Track 2.2 GitHub Actions artifact without echoing its passphrase."""
from __future__ import annotations

import argparse
import getpass
import subprocess
import tarfile
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("encrypted_file", type=Path, help="track22-state.tar.gz.enc from the downloaded artifact")
    parser.add_argument("output_folder", type=Path, help="new folder for the saved data and results")
    args = parser.parse_args()
    if not args.encrypted_file.is_file():
        parser.error(f"encrypted file not found: {args.encrypted_file}")
    if args.output_folder.exists():
        parser.error(f"output folder already exists: {args.output_folder}")
    passphrase = getpass.getpass("Artifact passphrase: ")
    if not passphrase:
        parser.error("passphrase is required")
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "track22-state.tar.gz"
        subprocess.run(
            ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
             "-in", str(args.encrypted_file), "-out", str(archive), "-pass", "stdin"],
            input=passphrase + "\n", text=True, check=True,
        )
        with tarfile.open(archive, "r:gz") as bundle:
            destination = args.output_folder.resolve()
            for member in bundle.getmembers():
                target = (destination / member.name).resolve()
                if not target.is_relative_to(destination) or not (member.isfile() or member.isdir()):
                    raise ValueError(f"unsafe artifact path: {member.name}")
            args.output_folder.mkdir(parents=True)
            bundle.extractall(args.output_folder)
    print(args.output_folder.resolve())


if __name__ == "__main__":
    main()
