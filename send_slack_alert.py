import requests

def send_slack_alert(top_jobs):
    webhook = os.getenv("SLACK_WEBHOOK")

    message = "*🔥 Top Job Matches Today:*\n"

    for job in top_jobs[:5]:
        message += f"- {job['title']} ({job['company']})\n{job['link']}\n\n"

    requests.post(webhook, json={"text": message})
