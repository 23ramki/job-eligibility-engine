import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_discord_webhook(jobs_list):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[notifier] DISCORD_WEBHOOK_URL not set in .env")
        return
    
    if not jobs_list:
        print("[notifier] No new jobs to notify.")
        return

    content = f"🚀 **{len(jobs_list)} New Eligible Jobs Found!**\n\n"
    # Send top 5 to avoid spam/limits
    for job in jobs_list[:5]:
        company = job.get("company_name", job.get("company", "Unknown"))
        content += f"**{job.get('job_title', 'Untitled')}** at {company}\n"
        content += f"Visa: {job.get('visa_status', 'Unknown')}\n"
        
        # Support various payload structures for URL
        apply_link = job.get('url') or job.get('apply_url') or job.get('link')
        if apply_link:
            content += f"[Apply Here]({apply_link})\n"
        content += "\n"

    payload = {"content": content}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"[notifier] Sent Discord notification for {len(jobs_list)} jobs.")
    except Exception as e:
        print(f"[notifier] Failed to send Discord webhook: {e}")

if __name__ == "__main__":
    # Test execution
    send_discord_webhook([
        {"job_title": "Data Analyst", "company_name": "Test Co", "visa_status": "Sponsored", "url": "https://example.com"}
    ])
