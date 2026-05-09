import os                                # FIX 4: was missing — caused NameError
import requests


def send_slack_alert(top_jobs):
    """
    Posts top job matches to a Slack channel via Incoming Webhook.

    Set SLACK_WEBHOOK in your .env file.
    Create a webhook at: api.slack.com/apps → Your App → Incoming Webhooks
    """
    webhook = os.getenv("SLACK_WEBHOOK")  # now works — os is imported

    if not webhook:
        print("[send_slack_alert] SLACK_WEBHOOK not set in .env — alert skipped.")
        return False

    if not top_jobs:
        print("[send_slack_alert] No jobs to send.")
        return False

    jobs_to_send = top_jobs[:5]
    message = f"*\U0001f525 {len(top_jobs)} New Job Matches — Top {len(jobs_to_send)} Today:*\n\n"

    for i, job in enumerate(jobs_to_send, 1):
        fit    = job.get("Fit Score", "N/A")
        salary = job.get("Salary", "")
        salary_str = f"  |  \U0001f4b0 {salary}" if salary and salary != "N/A" else ""
        message += (
            f"*{i}. {job.get('title', '')}* \u2014 {job.get('company', '')}\n"
            f"   \U0001f4cd {job.get('location', '')}  |  "
            f"\U0001f3af Fit: *{fit}/10*{salary_str}\n"
            f"   \U0001f517 {job.get('link', '')}\n\n"
        )

    try:
        response = requests.post(
            webhook,
            json={"text": message},
            timeout=10
        )
        response.raise_for_status()
        print(f"[send_slack_alert] Slack alert sent for {len(jobs_to_send)} jobs.")
        return True
    except requests.RequestException as e:
        print(f"[send_slack_alert] Failed to post to Slack: {e}")
        return False
