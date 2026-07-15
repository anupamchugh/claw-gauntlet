import argparse
import json
from collections.abc import Sequence

from claw_gauntlet.family import family_payload, manifest_for


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clawgauntlet")
    subparsers = parser.add_subparsers(dest="command", required=True)
    family = subparsers.add_parser("family")
    family.add_argument("--json", action="store_true", dest="as_json")
    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("name")
    manifest.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "family":
        payload = family_payload()
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "manifest":
        try:
            payload = manifest_for(args.name).to_dict()
        except KeyError as error:
            parser.error(error.args[0])
        print(json.dumps(payload, sort_keys=True))
        return 0
    return 2


def entrypoint() -> None:
    raise SystemExit(main())
