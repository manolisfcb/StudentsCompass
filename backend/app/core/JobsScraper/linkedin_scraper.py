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


#: How long one page request may take. Unchanged; named so the budget below
#: can be reasoned about against it.
PAGE_REQUEST_TIMEOUT_SECONDS = 15


def fetch_linkedin_jobs(
	keywords: str,
	location: str,
	limit: int = 25,
	remote: bool = False,
	throttle_seconds: float = 0.5,
	budget_seconds: float | None = None,
) -> List[JobPosting]:
	"""
	Scrape LinkedIn jobs (guest endpoint). Returns up to `limit` results.

	``budget_seconds`` caps the whole walk, not each request. Paging is a loop
	of 15-second requests separated by sleeps, so without a total budget one
	slow search could hold its worker for minutes while the caller had long
	since given up. When the budget runs out the pages collected so far are
	returned: a short answer beats an empty one, and the parsing and the shape
	of the result are the same either way.
	"""
	results: List[JobPosting] = []
	seen_urls = set()
	start = 0
	page_size = 25  # LinkedIn often returns 10-25 per page
	deadline = None if budget_seconds is None else time.monotonic() + budget_seconds

	def _remaining() -> Optional[float]:
		return None if deadline is None else deadline - time.monotonic()

	while len(results) < limit:
		remaining = _remaining()
		if remaining is not None and remaining <= 0:
			break

		url = _build_url(keywords, location, start, remote)
		request_timeout = PAGE_REQUEST_TIMEOUT_SECONDS
		if remaining is not None:
			request_timeout = min(request_timeout, remaining)
		resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=request_timeout)
		if resp.status_code != 200:
			break

		batch = _parse_jobs(resp.text)
		if not batch:
			break

		new_items = [j for j in batch if j.url and j.url not in seen_urls]
		for job in new_items:
			seen_urls.add(job.url)
			results.append(job)

		increment = len(batch)
		if increment <= 0 or not new_items:
			break

		if increment != page_size:
			page_size = increment
		start += increment

		if len(results) >= limit:
			break

		remaining = _remaining()
		if remaining is not None and remaining <= throttle_seconds:
			# Not enough left for another page after the pause; stop here
			# instead of sleeping into the deadline.
			break
		time.sleep(throttle_seconds)

	return results[:limit]
