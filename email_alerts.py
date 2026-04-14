import smtplib
from email.mime.text import MIMEText

def send_email(jobs):
    msg = MIMEText("\n\n".join([j["title"] + " - " + j["link"] for j in jobs[:5]]))
    msg["Subject"] = "Top Job Matches"
    msg["From"] = "you@email.com"
    msg["To"] = "you@email.com"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login("you@email.com", os.getenv("EMAIL_PASS"))
    server.send_message(msg)
    server.quit()
