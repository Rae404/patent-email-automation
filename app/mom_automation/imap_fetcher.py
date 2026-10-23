from __future__ import annotations

import imaplib
import json
import socket
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path

from .mail_parser import AttachmentInfo, EmailSample


class ImapConfigError(Exception):
    """配置文件缺字段或格式不对，给出中文提示。"""


class ImapConnectionError(Exception):
    """连接、登录或读取邮箱失败，给出中文提示。"""


@dataclass
class ImapConfig:
    host: str
    port: int
    username: str
    password: str
    mailbox: str = "INBOX"
    search: str = "ALL"
    use_ssl: bool = True
    max_messages: int = 50


_PLACEHOLDER_VALUES = {
    "imap.example.com",
    "your-email@example.com",
    "邮箱授权码或应用专用密码，不建议填写网页登录密码",
}


def load_imap_config(path: Path) -> ImapConfig:
    if not path.exists():
        raise ImapConfigError(
            f"找不到邮箱配置文件：{path}\n"
            "请先复制模板：cp config/imap_config.example.json "
            "config/imap_config.local.json，然后填写自己的邮箱信息。"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImapConfigError(
            f"邮箱配置文件不是合法的 JSON 格式：{path}\n错误详情：{exc}"
        ) from exc

    missing = [field for field in ("host", "username", "password") if not data.get(field)]
    if missing:
        raise ImapConfigError(
            "邮箱配置文件缺少必填字段：" + "、".join(missing) + f"\n请检查文件：{path}"
        )

    placeholder_fields = [
        field
        for field in ("host", "username", "password")
        if str(data.get(field, "")).strip() in _PLACEHOLDER_VALUES
    ]
    if placeholder_fields:
        raise ImapConfigError(
            "邮箱配置文件里还是模板中的示例值，尚未填写真实信息："
            + "、".join(placeholder_fields)
            + f"\n请编辑：{path}"
        )

    try:
        port = int(data.get("port", 993))
    except (TypeError, ValueError) as exc:
        raise ImapConfigError("配置文件里的 port（端口号）必须是数字，例如 993。") from exc

    try:
        max_messages = int(data.get("max_messages", 50))
    except (TypeError, ValueError) as exc:
        raise ImapConfigError("配置文件里的 max_messages（最多读取邮件数）必须是数字，例如 50。") from exc

    return ImapConfig(
        host=str(data["host"]).strip(),
        port=port,
        username=str(data["username"]).strip(),
        password=str(data["password"]),
        mailbox=data.get("mailbox", "INBOX"),
        search=data.get("search", "ALL"),
        use_ssl=bool(data.get("use_ssl", True)),
        max_messages=max_messages,
    )


def fetch_imap_samples(config: ImapConfig) -> list[EmailSample]:
    conn_cls = imaplib.IMAP4_SSL if config.use_ssl else imaplib.IMAP4
    try:
        mailbox = conn_cls(config.host, config.port)
    except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as exc:
        raise ImapConnectionError(
            f"无法连接到邮箱服务器 {config.host}:{config.port}。\n"
            "请检查：1) 服务器地址和端口是否正确；2) 网络是否正常；"
            "3) use_ssl 设置是否与端口匹配（SSL 常用 993，非 SSL 常用 143）。\n"
            f"原始错误：{exc}"
        ) from exc

    try:
        with mailbox:
            try:
                mailbox.login(config.username, config.password)
            except imaplib.IMAP4.error as exc:
                raise ImapConnectionError(
                    "登录邮箱失败，用户名或密码不正确。\n"
                    "很多邮箱（如 QQ、163、Gmail）不能直接用登录密码，需要在邮箱设置里开启 "
                    "IMAP/SMTP 服务并生成“授权码”或“应用专用密码”，再填到配置文件的 password 字段。\n"
                    f"原始错误：{exc}"
                ) from exc

            try:
                status, _ = mailbox.select(config.mailbox)
                if status != "OK":
                    raise imaplib.IMAP4.error(status)
            except imaplib.IMAP4.error as exc:
                raise ImapConnectionError(
                    f"打开邮箱文件夹「{config.mailbox}」失败，请确认文件夹名称是否正确"
                    "（例如中文邮箱常见的是 INBOX、已发送、Sent 等，注意大小写和名称是否需要加引号）。\n"
                    f"原始错误：{exc}"
                ) from exc

            status, data = mailbox.search(None, config.search)
            if status != "OK":
                raise ImapConnectionError(
                    f"邮件搜索失败，请检查配置文件中的 search 搜索条件是否正确：{config.search!r}"
                )
            message_ids = data[0].split()[-config.max_messages :]
            samples: list[EmailSample] = []
            for message_id in message_ids:
                status, msg_data = mailbox.fetch(message_id, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue
                raw = msg_data[0][1]
                samples.append(_email_sample_from_rfc822(raw))
            return samples
    except ImapConnectionError:
        raise
    except (socket.timeout, OSError) as exc:
        raise ImapConnectionError(f"读取邮件时网络中断，请重试。原始错误：{exc}") from exc


def _email_sample_from_rfc822(raw: bytes) -> EmailSample:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
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
                body_parts.append(str(part.get_content()))
            except Exception:
                pass
    return EmailSample(
        subject=subject,
        from_=from_,
        received_at=received_at,
        snippet="\n".join(body_parts)[:4000],
        attachments=attachments,
    )


def write_samples_json(samples: list[EmailSample], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for sample in samples:
        payload.append(
            {
                "from": sample.from_,
                "received_at": sample.received_at,
                "forwarded_at": sample.forwarded_at,
                "subject": sample.subject,
                "snippet": sample.snippet,
                "attachments": [
                    {"filename": attachment.filename}
                    for attachment in (sample.attachments or [])
                ],
            }
        )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

