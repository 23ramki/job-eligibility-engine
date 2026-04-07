# Job Eligibility Engine & Automated CRM

An automated, LLM-powered Job CRM that tracks your job applications, extracts requirements directly from job URLs, and perfectly tailors your resume and cover letters based on deep fit analysis.

## Features
- **One-Click Job Extraction**: Paste a LinkedIn/Indeed URL to scrape job descriptions, salaries, and visa expectations instantly.
- **Kanban Pipeline**: Track your applications visually across New, Applied, Interviewing, and Rejected stages.
- **Deep Fit Analysis (Powered by Gemini)**: Compares your master resume to the job description and asks you clarifying questions where necessary.
- **Tailored Resumes**: Automatically generates ATS-friendly, hyper-tailored PDF resumes matching the job's exact requirements without fabricating experience.
- **Automated Cover Letters**: Writes targeted cover letters designed to bypass generic AI detectors.
- **Discord Alerts**: Optional headless notification system for sponsored/top-tier jobs.

## Installation

### Prerequisites
- Python 3.9+
- A Google Gemini API Key
- (Optional) A TheirStack API Key
- (Optional) A Discord Webhook URL for alerts

### Setup
1. Clone this repository.
```bash
git clone <your-repo-link>
cd <repo-directory>
```

2. Create a virtual environment and load dependencies.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
*(Note: Be sure to install standard Streamlit requirements including `streamlit`, `google-generativeai`, `fpdf2`, `beautifulsoup4`, `requests`)*

3. Set up your environment variables.
Rename `.env.example` to `.env` and fill in your keys:
```bash
mv .env.example .env
```

4. Add your "Master Vault" Resume.
Edit the file `data/master_resume.txt`. Add your full career history, absolutely every bullet point you have. At the very bottom, locate the `--- AUTHOR TONE REFERENCE ---` and configure your exact writing style rules. Gemini read this to write *like you*.

## Running the App

Start the Streamlit dashboard on your local machine:
```bash
streamlit run app.py
```
