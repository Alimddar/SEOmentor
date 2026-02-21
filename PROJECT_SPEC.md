SEOmentor – AI SEO Roadmap Generator

1. Project Overview

SEOmentor is an AI-powered micro SaaS that:
	•	Analyzes a website homepage
	•	Extracts key SEO metrics
	•	Identifies main SEO weaknesses
	•	Detects competitors
	•	Finds keyword/content gaps
	•	Generates a personalized 30-day SEO execution roadmap

The goal is to help small and medium businesses understand exactly what they should do daily to improve their SEO.

This is a hackathon MVP. Keep implementation simple and clean.

⸻

2. Scope (IMPORTANT)

This is a hackathon MVP.

DO NOT implement:
	•	Authentication
	•	Payment systems
	•	Multi-page crawling
	•	Real SERP scraping
	•	Real backlink tracking
	•	External SEO APIs

Only analyze the homepage of the provided URL.

Focus on:
	•	Clean architecture
	•	AI integration
	•	Clear structured output
	•	Working end-to-end demo

⸻

3. Tech Stack

Backend
	•	FastAPI
	•	requests
	•	BeautifulSoup4
	•	OpenAI API (or compatible LLM API)
	•	SQLite (simple file-based DB)

Frontend
	•	React (Vite)
	•	TailwindCSS
	•	Axios for API calls

⸻

4. Backend Architecture

Create the following folder structure:

backend/
 ├── main.py
 ├── scraper.py
 ├── ai_service.py
 ├── database.py
 ├── models.py
 └── schemas.py

Keep architecture modular but simple.

⸻

5. Backend API Endpoints

POST /analyze

Request Body:

{
  "url": "https://example.com",
  "country": "Azerbaijan",
  "language": "English"
}

Pipeline:
	1.	Scrape homepage
	2.	Extract SEO metrics
	3.	Send structured data to AI service
	4.	Receive structured JSON response
	5.	Store result in database
	6.	Return project_id

Response:

{
  "project_id": 1
}


⸻

GET /project/{id}

Returns full stored SEO analysis:

{
  "seo_score": number,
  "issues": [],
  "competitors": [],
  "keyword_gaps": [],
  "roadmap": []
}


⸻

6. Scraper Requirements

In scraper.py, implement homepage analysis only.

Extract:
	•	Title
	•	Meta description
	•	H1 count
	•	H2 count
	•	Word count (visible text only)
	•	Number of internal links
	•	Number of images without alt attribute

Return structured dictionary:

{
  "title": "...",
  "meta_description": "...",
  "h1_count": 1,
  "h2_count": 3,
  "word_count": 850,
  "internal_links": 12,
  "missing_alt_images": 4
}

Do NOT crawl subpages.

⸻

7. AI Service Requirements

In ai_service.py:

Use LLM to analyze structured SEO data.

System Role

“You are an expert SEO strategist. Always return strict JSON only.”

User Prompt Template

Website URL: {url}

Country: {country}
Language: {language}

Extracted SEO Data:
Title: {title}
Meta Description: {meta_description}
H1 Count: {h1_count}
H2 Count: {h2_count}
Word Count: {word_count}
Internal Links: {internal_links}
Images Missing Alt: {missing_alt_images}

Based on this:

1. Generate SEO score (0-100)
2. List key SEO issues
3. Identify 5 realistic competitors in this country
4. Identify keyword/content gaps
5. Generate a structured 30-day SEO roadmap (one task per day)

Return strict JSON only in this format:

{
  "seo_score": number,
  "issues": ["..."],
  "competitors": [
    { "name": "...", "reason": "..." }
  ],
  "keyword_gaps": ["..."],
  "roadmap": [
    { "day": 1, "task": "..." }
  ]
}

No explanations. JSON only.

Use temperature 0.4 for stable output.

Validate JSON before saving.

⸻

8. Database

Use SQLite.

Create table:

projects
- id (integer, primary key)
- url (text)
- result_json (text)
- created_at (datetime)

Store AI response JSON as string.

Keep database logic simple.

⸻

9. Frontend Pages

Page 1: Landing Page
	•	Project name: SEOmentor
	•	Tagline: “Your AI SEO Co-Founder”
	•	Button: “Analyze My Website”

⸻

Page 2: Analyze Page

Form fields:
	•	Website URL
	•	Country
	•	Language

On submit:
	•	Call POST /analyze
	•	Redirect to dashboard

⸻

Page 3: Dashboard

Sections:
	1.	SEO Score (large number or circle)
	2.	Issues (list of problems)
	3.	Competitors (name + reason)
	4.	Keyword Gaps (list)
	5.	30-Day Plan (checklist style grouped by weeks)

Make UI clean and minimal.

⸻

10. UX Flow
	1.	User enters website
	2.	Show loading screen:
	•	“Analyzing website…”
	•	“Finding competitors…”
	•	“Generating roadmap…”
	3.	Redirect to dashboard
	4.	Display structured results

⸻

11. Important Development Rules
	•	Keep code clean and modular
	•	Avoid overengineering
	•	Do not implement unnecessary features
	•	Prioritize working demo over perfection
	•	Ensure AI always returns valid JSON

⸻

12. Future Improvements (For Pitch Only)

Do NOT implement, but mention during presentation:
	•	Google Search Console integration
	•	Real keyword volume tracking
	•	Backlink monitoring
	•	Automated content generation
	•	Ranking tracking dashboard

⸻

END OF SPEC

⸻