import smtplib, ssl, mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional

def _attach_file(msg: MIMEMultipart, path: str, filename: Optional[str] = None):
    ctype, encoding = mimetypes.guess_type(path)
    if ctype is None or encoding is not None:
        ctype = 'application/octet-stream'
    maintype, subtype = ctype.split('/', 1)
    with open(path, 'rb') as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment', filename=filename or path.split('/')[-1])
    msg.attach(part)

def send_email(host: str, port: int, username: str, password: str,
               from_addr: str, to_addrs: List[str], subject: str, html_body: str,
               attachments: Optional[List[str]] = None,
               use_ssl: Optional[bool] = None, timeout: int = 60):
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = ', '.join(to_addrs)

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(alt)

    for p in attachments or []:
        try:
            _attach_file(msg, p)
        except Exception as e:
            print(f"[WARN] Attach failed for {p}: {e}")

    ctx = ssl.create_default_context()
    if use_ssl is None:
        use_ssl = (int(port) == 465)

    if use_ssl:
        with smtplib.SMTP_SSL(host, int(port), timeout=timeout, context=ctx) as server:
            server.login(username, password)
            server.sendmail(from_addr, to_addrs, msg.as_string())
    else:
        with smtplib.SMTP(host, int(port), timeout=timeout) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(username, password)
            server.sendmail(from_addr, to_addrs, msg.as_string())
