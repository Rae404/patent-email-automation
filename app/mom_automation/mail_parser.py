from __future__ import annotations

import json
import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable

from .normalization import compact_text, normalize_identifier
from .status_rules import StatusMatch, detect_status


APPLICATION_NO_RE = re.compile(
    r"(?<!\d)(20\d{10,13}(?:[.\-]?[0-9Xx])?)(?!\d)"
)

NOTICE_WORDS = [
    "发明专利证书",
    "专利证书",
    "专利申请受理通知书",
    "专利受理通知书转达",
    "办理登记手续通知书",
    "驳回决定通知书",
    "收费减缴审批通知书",
    "补正通知书",
    "审查意见通知书",
]


@dataclass
class AttachmentInfo:
    filename: str


@dataclass
class EmailSample:
    subject: str
    from_: str = ""
    received_at: str = ""
    forwarded_at: str = ""
    snippet: str = ""
    attachments: list[AttachmentInfo] | None = None


@dataclass
class ParsedMailEvent:
    source_subject: str
    application_no: str
    normalized_no: str
    title: str
    event: str
    suggested_status: str
    confidence: str
    legal_status_update: bool
    needs_confirmation: bool
    received_at: str
    forwarded_at: str
    attachment_names: list[str]
    duplicate_count: int = 1
    notes: str = ""

    @property
    def dedupe_key(self) -> str:
        attachments = "|".join(sorted(self.attachment_names))
        return f"{self.normalized_no}|{self.event}|{attachments}"


def load_samples_json(path: Path) -> list[EmailSample]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    samples: list[EmailSample] = []
    for item in raw:
        attachments = [
            AttachmentInfo(filename=a["filename"] if isinstance(a, dict) else str(a))
            for a in item.get("attachments", [])
        ]
        samples.append(
            EmailSample(
                subject=item.get("subject", ""),
                from_=item.get("from", item.get("from_", "")),
                received_at=item.get("received_at", ""),
                forwarded_at=item.get("forwarded_at", ""),
                snippet=item.get("snippet", ""),
                attachments=attachments,
            )
        )
    return samples


def load_eml_folder(path: Path) -> list[EmailSample]:
    samples: list[EmailSample] = []
    for eml in sorted(path.glob("*.eml")):
        msg = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
        subject = str(msg.get("subject", ""))
        from_ = str(msg.get("from", ""))
        received_at = str(msg.get("date", ""))
        body_parts: list[str] = []
        attachments: list[AttachmentInfo] = []
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                attachments.append(AttachmentInfo(filename=filename))
                continue
            if part.get_content_type() == "text/plain":
                try:
                    body_parts.append(part.get_content())
                except Exception:
                    pass
        samples.append(
            EmailSample(
                subject=subject,
                from_=from_,
                received_at=received_at,
                snippet="\n".join(body_parts)[:4000],
                attachments=attachments,
            )
        )
    return samples


def extract_application_numbers(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in APPLICATION_NO_RE.finditer(text):
        raw = match.group(1).strip(" -_")
        normalized = normalize_identifier(raw)
        if len(normalized) < 12:
            continue
        if normalized not in seen:
            found.append(raw)
            seen.add(normalized)
    return found


def extract_forwarded_date(text: str) -> str:
    match = re.search(r"发送日期[:：]\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}\s+[0-9:]{4,8})", text)
    return match.group(1) if match else ""


def strip_fw(subject: str) -> str:
    return re.sub(r"^(Fw|Fwd|转发)[:：]\s*", "", subject, flags=re.I).strip()


def extract_title(text: str, app_no: str) -> str:
    subject = strip_fw(text)
    match = re.search(r"名称[:：](.+?)[；;]\s*申请号[:：]", subject)
    if match:
        return match.group(1).strip()

    # From text after application number until the first known notice word.
    norm_app = re.escape(app_no)
    match = re.search(norm_app + r"\s*(.+)", subject)
    candidate = match.group(1) if match else subject
    for word in NOTICE_WORDS:
        idx = candidate.find(word)
        if idx >= 0:
            candidate = candidate[:idx]
            break
    candidate = re.sub(r"PCN\d+", "", candidate)
    candidate = candidate.strip(" -_；;")
    return candidate


def parse_sample(sample: EmailSample) -> list[ParsedMailEvent]:
    attachments = sample.attachments or []
    attachment_names = [a.filename for a in attachments]
    combined_text = "\n".join([sample.subject, sample.snippet, *attachment_names])
    numbers = extract_application_numbers(combined_text)

    events: list[ParsedMailEvent] = []
    if not numbers:
        status = detect_status(combined_text)
        events.append(
            _event_from_status(
                sample,
                status,
                "",
                "",
                "未识别到申请号/登记号",
            )
        )
        return events

    # First pass: one primary event from subject/body.
    primary_status = detect_status(sample.subject + "\n" + sample.snippet)
    primary_no = numbers[0]
    if primary_status:
        events.append(_event_from_status(sample, primary_status, primary_no, combined_text))

    # Additional attachment-only events such as fee-reduction notices.
    for attachment in attachments:
        attachment_status = detect_status(attachment.filename)
        attachment_numbers = extract_application_numbers(attachment.filename)
        if not attachment_status or not attachment_numbers:
            continue
        event = _event_from_status(
            EmailSample(
                subject=sample.subject,
                from_=sample.from_,
                received_at=sample.received_at,
                forwarded_at=sample.forwarded_at,
                snippet=sample.snippet,
                attachments=[attachment],
            ),
            attachment_status,
            attachment_numbers[0],
            attachment.filename,
        )
        if attachment_status.event == (primary_status.event if primary_status else "") and any(
            e.normalized_no == event.normalized_no and e.event == event.event for e in events
        ):
            continue
        if not any(e.dedupe_key == event.dedupe_key for e in events):
            events.append(event)

    if not events:
        events.append(
            _event_from_status(sample, None, primary_no, combined_text, "未识别到状态事件")
        )
    return events


def _event_from_status(
    sample: EmailSample,
    status: StatusMatch | None,
    app_no: str,
    title_source: str,
    notes: str = "",
) -> ParsedMailEvent:
    attachment_names = [a.filename for a in (sample.attachments or [])]
    return ParsedMailEvent(
        source_subject=sample.subject,
        application_no=app_no,
        normalized_no=normalize_identifier(app_no),
        title=extract_title(title_source or sample.subject, app_no) if app_no else "",
        event=status.event if status else "",
        suggested_status=status.suggested_status if status else "",
        confidence=status.confidence if status else "低",
        legal_status_update=status.legal_status_update if status else False,
        needs_confirmation=True if status is None else status.needs_confirmation,
        received_at=sample.received_at,
        forwarded_at=sample.forwarded_at or extract_forwarded_date(sample.snippet),
        attachment_names=attachment_names,
        notes=notes,
    )


def parse_samples(samples: Iterable[EmailSample]) -> list[ParsedMailEvent]:
    events: list[ParsedMailEvent] = []
    for sample in samples:
        events.extend(parse_sample(sample))
    return dedupe_events(events)


def dedupe_events(events: Iterable[ParsedMailEvent]) -> list[ParsedMailEvent]:
    grouped: dict[str, ParsedMailEvent] = {}
    for event in events:
        key = event.dedupe_key
        if key not in grouped:
            grouped[key] = event
            continue
        grouped[key].duplicate_count += 1
        existing_notes = grouped[key].notes
        grouped[key].notes = "; ".join(
            n for n in [existing_notes, f"重复邮件 x{grouped[key].duplicate_count}"] if n
        )
    return list(grouped.values())
