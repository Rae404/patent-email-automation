# Patent Email Automation · 为妈妈定制的专利邮件办公助手

A local Python prototype I originally built for my mum to reduce repetitive work in her patent email and Excel workflow.

**This project was designed around one person's working process, Chinese notification formats, and spreadsheet conventions. Reusing it for another workflow may require changes to the source code as well as configuration.** It is shared as a personal project and a starting point for adaptation.

这个项目最初是专门给我妈妈做的，目的是减少她从专利通知邮件中查找信息、再手动核对 Excel 的重复工作。邮件格式、识别关键词、表头和状态处理都围绕她的实际需求设计。其他人使用前，需要根据自己的邮件和表格调整配置，必要时修改源码。

## What it does / 当前功能

- Reads local JSON samples, exported `.eml` files, or messages from an IMAP mailbox.
- Extracts application numbers and suggested events from Chinese subjects, plain-text bodies, and attachment filenames.
- Normalises identifiers, groups duplicate events, and matches identifiers to Excel rows.
- Produces an Excel preview with items requiring review highlighted.
- Optionally applies eligible status updates to a separate workbook copy and writes an update-record sheet.
- Includes an interactive Chinese command-line wizard. No AI model or API key is required.

## Project status / 项目阶段

An early, task-specific prototype. It has no desktop GUI, packaged Windows executable, recurring scheduler, PDF-content extraction, or linked-workbook synchronisation. The current matcher uses identifiers; it does not implement fuzzy name matching. Registration-number extraction is limited by the current regular expression and is not a complete software-copyright parser.

Confidence labels and event priorities come from hand-written rules. They are not statistical confidence scores. Review outputs before using them in a real workflow. This publication copy includes only synthetic samples; it does not include the original correspondence, business spreadsheets, outputs, or private development handover notes.

## Quick start / 快速开始

Requires Python 3.10 or newer. Run commands from the repository root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
python -m mom_automation parse-samples --input samples/emails.json --output outputs/preview.xlsx --log outputs/run.txt
python -m mom_automation wizard
```

The eight synthetic emails produce seven unique events. All sample names, dates, identifiers, and email addresses are fictional test values; identifier checksums are not validated.

### Use an Excel workbook

```bash
python -m mom_automation parse-samples --input samples/emails.json --workbook private/master.xlsx --output outputs/preview.xlsx
python -m mom_automation apply-preview --preview outputs/preview.xlsx --workbook private/master.xlsx --out outputs/master_updated_copy.xlsx
```

Keep the input workbook unchanged between preview generation and applying updates: the preview stores worksheet names and row numbers. Always choose a separate output path. The copy currently replaces an existing `自动化更新记录` sheet, and writing `.xlsx` through openpyxl may not preserve every advanced workbook feature. Use a backed-up, simple `.xlsx` workbook and inspect the result. There is no implemented chronological conflict resolution or separate timestamped-backup routine.

### Read an IMAP mailbox

Copy `config/imap_config.example.json` to `config/imap_config.local.json`, then edit the server, account, app password, mailbox, and search condition for your own provider.

```bash
python -m mom_automation fetch-imap --config config/imap_config.local.json --out private/mailbox.json
python -m mom_automation parse-samples --input private/mailbox.json --workbook private/master.xlsx --output outputs/preview.xlsx
```

The local configuration contains a password in plain text. Keep it private. IMAP currently fetches full messages and may mark them read depending on server behaviour. Real emails, credentials, spreadsheets, and generated outputs belong in ignored local folders.

### Read exported emails

```bash
python -m mom_automation parse-eml-folder --input private/eml --output outputs/preview.xlsx
```

## Adapting it / 换一个人使用，要改哪里？

| Requirement / 需求 | Where to change / 修改位置 |
| --- | --- |
| Mail server, login, folder, search scope / 邮箱参数 | `config/imap_config.local.json` |
| Recognised notice keywords and suggested states / 邮件关键词、状态、人工确认规则 | `app/mom_automation/status_rules.py` |
| Number formats, title extraction, forwarded dates, deduplication / 编号、标题、日期和去重 | `app/mom_automation/mail_parser.py`, `normalization.py` |
| Workbook column names and matching / Excel 表头和匹配方式 | `app/mom_automation/excel_matcher.py` |
| Preview columns and update behaviour / 预览输出和写回规则 | `app/mom_automation/preview_writer.py`, `apply_preview.py` |
| Chinese prompts and default paths / 向导提示和默认路径 | `app/mom_automation/wizard.py` |

Changing credentials and paths only requires configuration. Different mail templates, table layouts, status meanings, or approval rules can require source changes. Test those changes on synthetic emails and workbook copies first.

## Validation / 验证

```bash
python -m unittest discover -s tests -v
```

The existing three unit tests cover identifier normalisation, sample parsing/deduplication, and applying a matching status to a workbook copy. They do not validate a real mailbox, every patent-notice format, or every spreadsheet layout.

## Publication notes / 上传说明

The original local project is kept separately. This copy replaces the original real-email fixtures and test identifiers with synthetic data and uses portable paths. Private documentation and generated business files are excluded. The included `.gitignore` helps keep local credentials and business files out of future commits; inspect the selected files before each upload.
