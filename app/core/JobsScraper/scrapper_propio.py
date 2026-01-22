"""
Lightweight LinkedIn Jobs scraper (no Apify).
Uses the public jobs-guest endpoint, so no login/cookies required.

Inputs:
- keywords: search terms (e.g., "data scientist", "python developer")
- location: free-text location (e.g., "New York, NY", "Remote")
- limit: max number of jobs to return
- remote: bool to prefer remote (uses LinkedIn's f_WT=2 filter)

Note: LinkedIn may change markup/endpoint; this scraper is best-effort.
"""

from dataclasses import dataclass
from typing import List, Optional
import math
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
	"AppleWebKit/537.36 (KHTML, like Gecko) "
	"Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class JobPosting:
	title: str
	company: str
	location: str
	url: str
	listed_at: Optional[str]


def _build_url(keywords: str, location: str, start: int, remote: bool) -> str:
	base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
	params = {
		"keywords": keywords,
		"location": location,
		"start": start,
	}
	if remote:
		# LinkedIn remote filter (work from home)
		params["f_WT"] = "2"
	return f"{base}?{urllib.parse.urlencode(params)}"


def _parse_jobs(html: str) -> List[JobPosting]:
	soup = BeautifulSoup(html, "html.parser")
	cards = soup.select("div.base-card")
	jobs: List[JobPosting] = []
	for card in cards:
		title_el = card.select_one("h3.base-search-card__title")
		company_el = card.select_one("h4.base-search-card__subtitle")
		loc_el = card.select_one("span.job-search-card__location")
		link_el = card.select_one("a.base-card__full-link")
		time_el = card.select_one("time")

		title = title_el.get_text(strip=True) if title_el else ""
		company = company_el.get_text(strip=True) if company_el else ""
		location = loc_el.get_text(strip=True) if loc_el else ""
		url = link_el["href"] if link_el and link_el.has_attr("href") else ""
		listed_at = time_el["datetime"] if time_el and time_el.has_attr("datetime") else None

		if url:
			jobs.append(JobPosting(title, company, location, url, listed_at))
	return jobs


def fetch_linkedin_jobs(
	keywords: str,
	location: str,
	limit: int = 25,
	remote: bool = False,
	throttle_seconds: float = 0.5,
) -> List[JobPosting]:
	"""
	Scrape LinkedIn jobs (guest endpoint). Returns up to `limit` results.
	"""
	results: List[JobPosting] = []
	start = 0
	page_size = 25  # LinkedIn returns ~25 per page

	while len(results) < limit:
		url = _build_url(keywords, location, start, remote)
		resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
		if resp.status_code != 200:
			break

		batch = _parse_jobs(resp.text)
		if not batch:
			break

		results.extend(batch)
		start += page_size

		if len(batch) < page_size:
			break  # no more pages

		time.sleep(throttle_seconds)

	return results[:limit]


if __name__ == "__main__":
    jobs = fetch_linkedin_jobs(keywords="software engineer", location="Remote", limit=10, remote=True)
    for job in jobs:
        print(f"{job.title} at {job.company} ({job.location})")
        # print(f"URL: {job.url}")
        print(f"Listed at: {job.listed_at}")
        print()