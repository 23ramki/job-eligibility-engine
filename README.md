# Job Eligibility Engine & CRM

An AI-powered job application tracker that scores your resume against real job postings, tailors your resume and cover letter for each role, and keeps everything organized in a drag-and-drop Kanban board.

**No cloud subscription. Runs entirely on your laptop. Free AI APIs included.**

---

## What It Does

- **Pulls live job listings** from any URL (LinkedIn, Indeed, company pages) and saves them to your personal database
- **Scores every job** against your master resume so you know which roles are worth your time before you apply
- **Generates tailored resumes** — rewrites your resume to match each job's exact keywords and requirements, without making anything up
- **Writes cover letters** in seconds
- **Kanban board** to drag jobs between New → Applied → Interviewing → Rejected
- **Usage tracker** so you never accidentally blow through your free API quota

---

## What You'll Need Before Starting

1. **A computer running macOS, Windows, or Linux**
2. **Python 3.9 or newer** — check by opening a terminal and typing `python3 --version`. If you get an error, download it from [python.org](https://python.org).
3. **At least one free AI API key** — you only need one of these:
   - **Groq** (recommended, very fast): Sign up free at [console.groq.com](https://console.groq.com) → click "API Keys" → "Create API Key"
   - **Google Gemini**: Sign up free at [aistudio.google.com](https://aistudio.google.com/app/apikey) → click "Get API key"
4. *(Optional)* A **TheirStack API key** if you want the app to fetch new job listings automatically: [theirstack.com](https://theirstack.com)

---

## Installation — Step by Step

### Step 1: Download the project

Open a terminal (on Mac: press `Cmd + Space`, type "Terminal", hit Enter) and run:

```bash
git clone https://github.com/23ramki/job-eligibility-engine.git
cd job-eligibility-engine
```

If you don't have git, download the zip from the green "Code" button on this page and unzip it, then `cd` into the folder.

---

### Step 2: Create a virtual environment

This keeps the app's dependencies isolated from the rest of your computer:

```bash
python3 -m venv venv
```

Now activate it:

- **Mac / Linux:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

You'll see `(venv)` appear at the start of your terminal prompt. That means it worked.

---

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

This installs everything the app needs. It may take 1–2 minutes.

---

### Step 4: Add your API keys

Copy the example config file:

- **Mac / Linux:**
  ```bash
  cp .env.example .env
  ```
- **Windows:**
  ```bash
  copy .env.example .env
  ```

Now open the `.env` file in any text editor (Notepad, TextEdit, VS Code — anything works) and paste in your keys:

```
GROQ_API_KEY=paste_your_groq_key_here
GEMINI_API_KEY=paste_your_gemini_key_here
```

You only need one of those two. Save the file.

> **Important:** Never share your `.env` file or commit it to GitHub. It's already in `.gitignore` so git will ignore it automatically.

---

### Step 5: Add your master resume

Create a file at `data/master_resume.txt` (the `data/` folder already exists in the project).

Paste your **complete career history** into this file — every job, every bullet point, every skill, every certification. Don't hold back. The more detail you give it, the better the tailored resumes will be. **The AI only uses facts from this file, so it will NEVER fabricate experience.**  

---

### Step 6: Run the app

```bash
streamlit run app.py
```

Your browser will automatically open to `http://localhost:8501`. If it doesn't, open that URL manually.

---

## Using the App

### First time setup
When the app opens, look for the **sidebar on the left**. Paste your Groq or Gemini API key there if you haven't set up the `.env` file yet — you can also enter keys directly in the UI.

### Adding jobs
1. Go to the **"Add Jobs"** tab
2. Paste a job listing URL and click Fetch — the app will scrape the title, company, description, and salary automatically
3. Or use **"Fetch from TheirStack"** to pull a batch of new listings at once (requires TheirStack API key)

### Scoring and tailoring
1. Click any job card to open it
2. Hit **"Score Fit"** — the AI compares the job requirements to your resume and gives it a score (0–100) with a reason
3. Hit **"Analyze Fit"** for a deeper breakdown — it'll ask you clarifying questions to surface experience your resume might not highlight clearly
4. Hit **"Generate Resume"** to get a tailored, one-page resume as a PDF download
5. Hit **"Cover Letter"** for a matching cover letter

### Kanban board
Drag job cards between columns to track your pipeline: **New → Applied → Interviewing → Rejected**

---

## Troubleshooting

**`ModuleNotFoundError`** — You forgot to activate the virtual environment. Run `source venv/bin/activate` (Mac/Linux) or `venv\Scripts\activate` (Windows) first.

**`streamlit: command not found`** — Same issue. Activate the venv first.

**API errors / "No API key set"** — Double-check your `.env` file. Make sure there are no spaces around the `=` sign: `GROQ_API_KEY=your_key` not `GROQ_API_KEY = your_key`.

**Blank Kanban board** — You haven't added any jobs yet. Go to the "Add Jobs" tab first.

---

## Project Structure

```
job-eligibility-engine/
├── app.py                  # Main Streamlit app
├── fetch_jobs.py           # TheirStack job fetching
├── requirements.txt        # Python dependencies
├── .env.example            # Config template (copy to .env)
├── data/                   # Your local database (gitignored)
│   └── master_resume.txt   # Your resume — add this yourself
└── src/
    ├── ollama_client.py    # Groq + Gemini API routing
    ├── llm_tailoring.py    # Resume & cover letter generation
    ├── state_manager.py    # SQLite job database
    ├── job_scraper.py      # URL scraping
    ├── pdf_generator.py    # PDF export
    ├── kanban_component.py # Drag-and-drop board
    ├── usage_tracker.py    # API quota monitoring
    └── notifier.py         # Discord alerts (optional)
```

---

## Free Tier Limits

Both Groq and Gemini have generous free tiers. The app tracks your daily usage automatically:

| Provider | Free Tokens/Day | Free Requests/Day |
|----------|----------------|-------------------|
| Groq     | ~28,800         | 500               |
| Gemini   | ~250,000        | 1,500             |

The app automatically routes long prompts (resume generation) to Gemini and short prompts (fit scoring) to Groq to make the most of both.
