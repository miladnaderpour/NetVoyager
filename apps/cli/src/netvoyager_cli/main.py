"""CLI entry point. API commands will be added after the HTTP contract exists."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="netvoyager", description="NetVoyager API client")
    parser.add_argument("--version", action="version", version="NetVoyager CLI 0.1.0")
    parser.parse_args()
