from __future__ import annotations

import argparse
from pathlib import Path

from .excel_matcher import match_events_to_workbook
from .apply_preview import apply_preview
from .imap_fetcher import (
    ImapConfigError,
    ImapConnectionError,
    fetch_imap_samples,
    load_imap_config,
    write_samples_json,
)
from .mail_parser import load_eml_folder, load_samples_json, parse_samples
from .preview_writer import write_log, write_preview
from .wizard import run_wizard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mom_automation")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_samples = sub.add_parser("parse-samples", help="Parse JSON email samples and write update preview.")
    parse_samples.add_argument("--input", required=True, type=Path)
    parse_samples.add_argument("--workbook", type=Path)
    parse_samples.add_argument("--output", required=True, type=Path)
    parse_samples.add_argument("--log", type=Path)

    parse_eml = sub.add_parser("parse-eml-folder", help="Parse .eml files and write update preview.")
    parse_eml.add_argument("--input", required=True, type=Path)
    parse_eml.add_argument("--workbook", type=Path)
    parse_eml.add_argument("--output", required=True, type=Path)
    parse_eml.add_argument("--log", type=Path)

    apply = sub.add_parser("apply-preview", help="Apply safe preview rows to a workbook copy.")
    apply.add_argument("--preview", required=True, type=Path)
    apply.add_argument("--workbook", required=True, type=Path)
    apply.add_argument("--out", required=True, type=Path)

    fetch_imap = sub.add_parser("fetch-imap", help="Fetch messages from an IMAP mailbox into samples JSON.")
    fetch_imap.add_argument("--config", required=True, type=Path)
    fetch_imap.add_argument("--out", required=True, type=Path)

    sub.add_parser("wizard", help="交互式中文向导：读取邮件、匹配主表、生成预览和副本。")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "wizard":
        return run_wizard()

    if args.command == "apply-preview":
        summary = apply_preview(args.preview, args.workbook, args.out)
        print(f"updated_rows={summary.updated_rows}")
        print(f"skipped_rows={summary.skipped_rows}")
        print(f"output={summary.copied_to}")
        return 0

    if args.command == "fetch-imap":
        try:
            config = load_imap_config(args.config)
            samples = fetch_imap_samples(config)
        except (ImapConfigError, ImapConnectionError) as exc:
            print(f"错误：{exc}")
            return 1
        write_samples_json(samples, args.out)
        print(f"fetched_messages={len(samples)}")
        print(f"output={args.out}")
        return 0

    if args.command == "parse-samples":
        samples = load_samples_json(args.input)
    elif args.command == "parse-eml-folder":
        samples = load_eml_folder(args.input)
    else:
        raise ValueError(args.command)

    events = parse_samples(samples)
    matches = match_events_to_workbook(events, args.workbook)
    write_preview(events, matches, args.output)
    if args.log:
        write_log(events, matches, args.log)
    print(f"parsed_events={len(events)}")
    print(f"preview={args.output}")
    if args.log:
        print(f"log={args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
