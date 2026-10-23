from __future__ import annotations

from pathlib import Path
from typing import Callable

from .apply_preview import apply_preview
from .excel_matcher import match_events_to_workbook
from .imap_fetcher import (
    ImapConfigError,
    ImapConnectionError,
    fetch_imap_samples,
    load_imap_config,
    write_samples_json,
)
from .mail_parser import EmailSample, load_eml_folder, load_samples_json, parse_samples
from .preview_writer import write_log, write_preview


def _ask(prompt: str, default: str = "", input_fn: Callable[[str], str] = input) -> str:
    suffix = f"（默认：{default}）" if default else ""
    raw = input_fn(f"{prompt}{suffix}: ").strip()
    return raw or default


def _ask_choice(
    prompt: str,
    options: list[tuple[str, str]],
    input_fn: Callable[[str], str] = input,
) -> str:
    print(prompt)
    for key, label in options:
        print(f"  {key}. {label}")
    valid_keys = {key for key, _ in options}
    while True:
        raw = input_fn("请输入编号: ").strip()
        if raw in valid_keys:
            return raw
        print(f"输入无效，请输入 {', '.join(sorted(valid_keys))} 中的一个。")


def run_wizard(input_fn: Callable[[str], str] = input, print_fn: Callable[[str], None] = print) -> int:
    print_fn("=== 妈妈办公自动化 - 中文向导 ===")
    print_fn("本工具只生成预览和副本，不会修改原始 Excel 表格。\n")

    source = _ask_choice(
        "第 1 步：选择邮件数据来源",
        [("1", "直接读取我的邮箱（IMAP）"), ("2", "读取本地 .eml 邮件文件夹"), ("3", "使用样本 JSON 文件")],
        input_fn,
    )

    samples: list[EmailSample]
    if source == "1":
        default_config = "config/imap_config.local.json"
        config_path_str = _ask("请输入邮箱配置文件路径", default_config, input_fn)
        config_path = Path(config_path_str)
        try:
            config = load_imap_config(config_path)
        except ImapConfigError as exc:
            print_fn(f"\n配置有问题，向导已停止：\n{exc}")
            return 1
        print_fn(f"正在连接邮箱 {config.host} ...")
        try:
            samples = fetch_imap_samples(config)
        except ImapConnectionError as exc:
            print_fn(f"\n连接或读取邮箱失败，向导已停止：\n{exc}")
            return 1
        print_fn(f"成功读取 {len(samples)} 封邮件。")
        cache_path_str = _ask(
            "是否要把读取到的邮件另存为本地样本 JSON（便于以后离线复用）？留空则不保存",
            "",
            input_fn,
        )
        if cache_path_str:
            write_samples_json(samples, Path(cache_path_str))
            print_fn(f"已保存到：{cache_path_str}")
    elif source == "2":
        folder_str = _ask("请输入 .eml 邮件文件夹路径", "", input_fn)
        folder = Path(folder_str)
        if not folder.is_dir():
            print_fn(f"\n找不到文件夹：{folder}，向导已停止。")
            return 1
        samples = load_eml_folder(folder)
        print_fn(f"成功读取 {len(samples)} 封邮件。")
    else:
        sample_str = _ask("请输入样本 JSON 文件路径", "samples/emails.json", input_fn)
        sample_path = Path(sample_str)
        if not sample_path.exists():
            print_fn(f"\n找不到文件：{sample_path}，向导已停止。")
            return 1
        samples = load_samples_json(sample_path)
        print_fn(f"成功读取 {len(samples)} 封邮件。")

    if not samples:
        print_fn("\n没有读取到任何邮件，向导结束。")
        return 0

    print_fn("\n第 2 步：选择专利/知识产权主表 Excel（可选）")
    workbook_str = _ask("请输入 Excel 主表路径，留空则跳过匹配，只做邮件解析", "", input_fn)
    workbook_path = Path(workbook_str) if workbook_str else None
    if workbook_path is not None and not workbook_path.exists():
        print_fn(f"\n找不到 Excel 文件：{workbook_path}，向导已停止。")
        return 1

    print_fn("\n第 3 步：选择输出目录")
    output_dir_str = _ask("结果文件保存到哪个目录", "outputs", input_fn)
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    print_fn("\n正在解析邮件并生成预览 ...")
    events = parse_samples(samples)
    matches = match_events_to_workbook(events, workbook_path)

    preview_path = output_dir / "更新预览.xlsx"
    log_path = output_dir / "运行日志.txt"
    write_preview(events, matches, preview_path)
    write_log(events, matches, log_path)
    print_fn(f"已生成预览：{preview_path}")
    print_fn(f"已生成运行日志：{log_path}")

    if workbook_path is not None:
        apply_choice = _ask_choice(
            "\n第 4 步：是否把预览中「不需要人工确认」的安全更新写入主表副本？（不会修改原表）",
            [("1", "是，生成副本"), ("2", "否，先人工检查预览再说")],
            input_fn,
        )
        if apply_choice == "1":
            copy_path = output_dir / "更新后的主表_副本.xlsx"
            summary = apply_preview(preview_path, workbook_path, copy_path)
            print_fn(f"已生成主表副本：{summary.copied_to}")
            print_fn(f"自动更新行数：{summary.updated_rows}")
            print_fn(f"跳过（待人工确认）行数：{summary.skipped_rows}")
            print_fn("原始 Excel 文件未被修改。")

    print_fn("\n完成。请先打开「更新预览.xlsx」核对标黄的待确认行，再决定是否采用副本表。")
    return 0


def main() -> int:
    return run_wizard()


if __name__ == "__main__":
    raise SystemExit(main())
