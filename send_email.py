import html
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _safe_url(url: str) -> str:
    """Allow only http/https URLs in href attributes; blank anything else."""
    url = url.strip()
    return url if url.startswith(("http://", "https://")) else "#"


def send_email(jobs, subject=None):
    """
    Sends a styled HTML email digest of the top job matches.

    Reads all config from environment variables (set in .env):
        EMAIL_SENDER    — Gmail address to send FROM
        EMAIL_RECIPIENT — address to send TO (can be same as sender)
        EMAIL_PASSWORD  — Gmail App Password (NOT your login password)
                          Generate at: myaccount.google.com/apppasswords
    """
    # FIX 3b: was hardcoded "you@email.com" — now reads from env
    sender    = os.getenv("EMAIL_SENDER")
    recipient = os.getenv("EMAIL_RECIPIENT")
    password  = os.getenv("EMAIL_PASSWORD")

    missing = [k for k, v in {
        "EMAIL_SENDER":    sender,
        "EMAIL_RECIPIENT": recipient,
        "EMAIL_PASSWORD":  password
    }.items() if not v]

    if missing:
        print(f"[send_email] Missing env vars: {missing} — email not sent.")
        return False

    if not jobs:
        print("[send_email] No jobs to send.")
        return False

    top_jobs = jobs[:10]
    subject  = subject or f"\U0001f50d Daily Job Digest — {len(jobs)} New Matches"

    # FIX 3c: README promised "styled HTML email digests" — was plain text
    rows_html = ""
    for i, job in enumerate(top_jobs, 1):
        # Escape all external data before inserting into HTML
        title   = html.escape(str(job.get("title",    "")))
        company = html.escape(str(job.get("company",  "")))
        loc     = html.escape(str(job.get("location", "")))
        fit     = html.escape(str(job.get("Fit Score", "N/A")))
        salary  = html.escape(str(job.get("Salary",   "N/A")))
        link    = _safe_url(job.get("link", ""))
        bg      = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        rows_html += f"""
        <tr style="background:{bg}">
          <td style="padding:10px;border-bottom:1px solid #eee;font-weight:bold;color:#0066cc">
            #{i}
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee">
            <a href="{link}" style="color:#0066cc;text-decoration:none;font-weight:bold">
              {title}
            </a>
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee">{loc}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;color:#2a7a2a;font-weight:bold">
            {fit}/10
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee">{salary}</td>
        </tr>"""

    html_body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;color:#333">
      <div style="background:#0066cc;padding:20px;border-radius:8px 8px 0 0">
        <h2 style="color:white;margin:0">\U0001f50d Daily Job Digest</h2>
        <p style="color:#cce0ff;margin:6px 0 0">
          {len(jobs)} new matches found &mdash; top {len(top_jobs)} shown below
        </p>
      </div>
      <table style="width:100%;border-collapse:collapse;border:1px solid #ddd;border-top:none">
        <thead>
          <tr style="background:#e8f0fe">
            <th style="padding:12px;text-align:left;border-bottom:2px solid #0066cc">#</th>
            <th style="padding:12px;text-align:left;border-bottom:2px solid #0066cc">Job Title</th>
            <th style="padding:12px;text-align:left;border-bottom:2px solid #0066cc">Company</th>
            <th style="padding:12px;text-align:left;border-bottom:2px solid #0066cc">Location</th>
            <th style="padding:12px;text-align:left;border-bottom:2px solid #0066cc">Fit Score</th>
            <th style="padding:12px;text-align:left;border-bottom:2px solid #0066cc">Est. Salary</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="color:#999;font-size:12px;padding:16px;border-top:1px solid #eee">
        Generated automatically by your Job Search Pipeline.
        All statuses default to "Not Applied".
      </p>
    </body>
    </html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"[send_email] Email sent to {recipient} with {len(top_jobs)} jobs.")
        return True
    except smtplib.SMTPAuthenticationError:
        print(
            "[send_email] Gmail auth failed.\n"
            "Make sure EMAIL_PASSWORD is a Gmail App Password, not your account password.\n"
            "Generate one at: myaccount.google.com/apppasswords"
        )
        return False
    except Exception as e:
        print(f"[send_email] Failed to send: {e}")
        return False
