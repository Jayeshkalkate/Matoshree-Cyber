import logging
import re
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from django.core.cache import cache
from urllib.parse import urljoin
import time

logger = logging.getLogger(__name__)

# ─── Use cloudscraper if available, else fallback to requests ───
try:
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True,
            'mobile': False
        }
    )
    logger.info("✅ cloudscraper loaded – will bypass 403/Cloudflare")
except ImportError:
    import requests
    scraper = requests
    logger.warning("⚠️ cloudscraper not installed – using requests (may get 403)")

# ─── Realistic headers (same as before, but consistent) ───
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

def fetch_with_retry(url, timeout=25, retries=3):
    """Fetch URL with retries using the selected scraper."""
    for attempt in range(retries):
        try:
            response = scraper.get(url, timeout=timeout, headers=HEADERS)
            response.raise_for_status()
            return response
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"Attempt {attempt+1}/{retries} for {url} failed: {e}. Retrying in {wait}s...")
            if attempt == retries - 1:
                raise
            time.sleep(wait)
    return None

# ════════════════════════════════════════════════════════════════
# 1. PRIMARY SCRAPERS – UNCHANGED LOGIC, ONLY NETWORK UPGRADED
# ════════════════════════════════════════════════════════════════

def fetch_majhinaukri_jobs():
    """Scrape genuine job listings from majhinaukri.in homepage."""
    url = "https://majhinaukri.in/"
    jobs = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')

        HEADING_BLACKLIST = {
            "वर्तमान भरती", "latest jobs", "view more", "prev", "next",
            "«", "»", "←", "→", "previous", "next page",
            "नवीनतम भरती", "ताज्या भरती", "नोकरीच्या जाहिराती",
            "popular departments", "government jobs", "private jobs"
        }
        JOB_KEYWORDS = {
            "bharti", "recruitment", "job", "vacancy", "notification",
            "भरती", "मेळावा", "नोकरी", "पद", "जागा", "नियुक्ति",
            "walk-in", "apply", "exam", "admit card", "result"
        }

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip()
            text_lower = text.lower()

            if not href.startswith('https://majhinaukri.in/'):
                continue
            if any(skip in href for skip in ['/category/', '/tag/', '/page/', '/wp-', '#', '?page=']):
                continue
            if any(phrase in text_lower for phrase in HEADING_BLACKLIST):
                continue
            if text.isdigit() or text_lower in ("prev", "next") or "view more" in text_lower:
                continue
            if len(text) < 5:
                continue

            has_date = re.search(r'/\d{4}/\d{2}/\d{2}/', href) is not None
            has_keyword = any(kw in text_lower for kw in JOB_KEYWORDS)
            if not (has_date or has_keyword):
                continue

            clean_title = text
            for prefix in ["latest jobs:", "वर्तमान भरती:", "ताज्या भरती:", "नवीनतम भरती:"]:
                if clean_title.lower().startswith(prefix):
                    clean_title = clean_title[len(prefix):].strip()
                    break

            last_date = None
            parent = a.parent
            if parent:
                parent_text = parent.get_text()
                date_match = re.search(r'(\d+)\s*(day|d|days?)\s*ago', parent_text, re.I)
                if date_match:
                    days_ago = int(date_match.group(1))
                    last_date = datetime.now().date() - timedelta(days=days_ago)
                else:
                    date_match = re.search(r'(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})', parent_text)
                    if date_match:
                        try:
                            last_date = datetime.strptime(date_match.group(1), '%d %b %Y').date()
                        except:
                            pass
                    else:
                        date_match = re.search(r'(\d{2}-\d{2}-\d{4})', parent_text)
                        if date_match:
                            try:
                                last_date = datetime.strptime(date_match.group(1), '%d-%m-%Y').date()
                            except:
                                pass

            jobs.append({
                'title': clean_title,
                'organization': 'Majhi Naukri',
                'description': '',
                'apply_link': href,
                'last_date': last_date,
                'source': 'majhinaukri'
            })

        # Deduplicate
        seen = set()
        unique = []
        for job in jobs:
            if job['apply_link'] not in seen:
                seen.add(job['apply_link'])
                unique.append(job)

        logger.info(f"Scraped {len(unique)} jobs from majhinaukri.in")
        return unique[:30]

    except Exception as e:
        logger.error(f"Error scraping majhinaukri.in: {e}")
        return []


def fetch_majhinaukri_updates():
    """Scrape job updates from majhinaukri.in/new-updates/."""
    url = "https://majhinaukri.in/new-updates/"
    jobs = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')

        pattern = r'(\d{2}/\d{2}/\d{4})\s*\|\s*([^<\n]+)'
        for element in soup.find_all(['li', 'p', 'div']):
            text = element.get_text(strip=True)
            match = re.search(pattern, text)
            if not match:
                continue
            date_str, title = match.groups()
            link_tag = element.find('a', href=True)
            link = link_tag['href'] if link_tag else '#'
            if link and not link.startswith('http'):
                link = urljoin('https://majhinaukri.in', link)

            try:
                last_date = datetime.strptime(date_str, '%d/%m/%Y').date()
            except ValueError:
                last_date = None

            jobs.append({
                'title': title.strip(),
                'organization': 'Majhi Naukri',
                'description': '',
                'apply_link': link,
                'last_date': last_date,
                'source': 'majhinaukri_updates'
            })

        if not jobs:
            html = response.text
            matches = re.findall(pattern, html)
            for date_str, title in matches:
                try:
                    last_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                except ValueError:
                    last_date = None
                jobs.append({
                    'title': title.strip(),
                    'organization': 'Majhi Naukri',
                    'description': '',
                    'apply_link': '#',
                    'last_date': last_date,
                    'source': 'majhinaukri_updates'
                })

        seen = set()
        unique = []
        for job in jobs:
            key = (job['title'], job['last_date'])
            if key not in seen:
                seen.add(key)
                unique.append(job)

        logger.info(f"Scraped {len(unique)} updates from majhinaukri.in/new-updates/")
        return unique[:30]

    except Exception as e:
        logger.error(f"Error scraping majhinaukri.in/new-updates/: {e}")
        return []


def fetch_govtjobsalert_jobs():
    """Scrape jobs from govtjobsalert.in Maharashtra page."""
    url = "https://govtjobsalert.in/maharashtra-govt-jobs/"
    jobs = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')

        items = soup.select('article') or soup.select('.job-list, .post, .entry-content ul li')
        for item in items:
            link_tag = item.find('a')
            if not link_tag:
                continue
            title = link_tag.text.strip()
            href = link_tag.get('href')
            if not href or len(title) < 5:
                continue
            if not href.startswith('http'):
                href = 'https://govtjobsalert.in' + href

            last_date = None
            item_text = item.get_text()
            date_match = re.search(r'Last Date:\s*(\d{2}\s+[A-Za-z]{3}\s+\d{4})', item_text, re.I)
            if date_match:
                try:
                    last_date = datetime.strptime(date_match.group(1), '%d %b %Y').date()
                except:
                    pass

            jobs.append({
                'title': title,
                'organization': 'Govt Jobs Alert',
                'description': '',
                'apply_link': href,
                'last_date': last_date,
                'source': 'govtjobsalert'
            })

        if not jobs:
            html = response.text
            pattern = r'Job Post[^\]]*?Last Date:\s*(\d{2}\s+[A-Za-z]{3}\s+\d{4})[^#]*###\s*([^)]+)\(([^)]+)\)'
            matches = re.findall(pattern, html)
            for last_date_str, title, link in matches:
                title = re.sub(r'^\[.*?\]\s*', '', title.strip())
                try:
                    last_date = datetime.strptime(last_date_str, '%d %b %Y').date()
                except:
                    last_date = None
                jobs.append({
                    'title': title,
                    'organization': 'Govt Jobs Alert',
                    'description': '',
                    'apply_link': link.strip(),
                    'last_date': last_date,
                    'source': 'govtjobsalert'
                })

        seen = set()
        unique = []
        for job in jobs:
            if job['apply_link'] not in seen:
                seen.add(job['apply_link'])
                unique.append(job)

        logger.info(f"Scraped {len(unique)} jobs from govtjobsalert.in")
        return unique[:30]

    except Exception as e:
        logger.error(f"Error scraping govtjobsalert.in: {e}")
        return []


def fetch_indgovtjobs_jobs():
    """Scrape jobs from mh.indgovtjobs.net (table format)."""
    url = "https://mh.indgovtjobs.net/"
    jobs = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')

        rows = soup.select('table tr')
        for row in rows:
            links = row.find_all('a')
            if not links:
                continue
            job_link = links[0]
            title = job_link.text.strip()
            href = job_link.get('href')
            if not href or len(title) < 5:
                continue
            if not href.startswith('http'):
                href = urljoin(url, href)

            cells = row.find_all('td')
            last_date = None
            vacancies = None
            for cell in cells:
                text = cell.text.strip()
                date_match = re.search(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', text)
                if date_match:
                    try:
                        last_date = datetime.strptime(date_match.group(1), '%d %b %Y').date()
                    except:
                        pass
                if re.match(r'^\d+$', text):
                    vacancies = text

            description = ""
            if vacancies:
                description += f"Vacancies: {vacancies}"
            if last_date:
                if description:
                    description += " | "
                description += f"Last Date: {last_date.strftime('%d %b %Y')}"

            jobs.append({
                'title': title,
                'organization': 'MH IndGovtJobs',
                'description': description,
                'apply_link': href,
                'last_date': last_date,
                'source': 'indgovtjobs'
            })

        if not jobs:
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.text.strip()
                if 'apply' in text.lower() or 'bharti' in text.lower():
                    parent = a.parent
                    if parent:
                        parent_text = parent.get_text()
                        title_match = re.search(r'([A-Za-z0-9\s\-–]+?(?:Bharti|Recruitment|Vacancy|भरती))', parent_text, re.I)
                        if title_match:
                            title = title_match.group(1).strip()
                            if len(title) > 5:
                                jobs.append({
                                    'title': title,
                                    'organization': 'MH IndGovtJobs',
                                    'description': '',
                                    'apply_link': href if href.startswith('http') else urljoin(url, href),
                                    'last_date': None,
                                    'source': 'indgovtjobs'
                                })

        seen = set()
        unique = []
        for job in jobs:
            if job['apply_link'] not in seen:
                seen.add(job['apply_link'])
                unique.append(job)

        logger.info(f"Scraped {len(unique)} jobs from mh.indgovtjobs.net")
        return unique[:30]

    except Exception as e:
        logger.error(f"Error scraping mh.indgovtjobs.net: {e}")
        return []


def fetch_mahasarkar_jobs():
    """Static fallback for mahasarkar.co.in (limited)."""
    url = "https://mahasarkar.co.in/"
    jobs = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')

        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'job' in script.string.lower():
                matches = re.findall(r'"title":"([^"]+)"', script.string)
                for title in matches[:20]:
                    if len(title) > 5 and any(kw in title.lower() for kw in ['bharti', 'recruitment', 'vacancy', 'भरती']):
                        jobs.append({
                            'title': title,
                            'organization': 'Mahasarkar',
                            'description': '',
                            'apply_link': url,
                            'last_date': None,
                            'source': 'mahasarkar'
                        })

        if not jobs:
            logger.warning("mahasarkar.co.in: No jobs found in static HTML.")

        seen = set()
        unique = []
        for job in jobs:
            key = job['title'] + job['apply_link']
            if key not in seen:
                seen.add(key)
                unique.append(job)

        logger.info(f"Scraped {len(unique)} jobs from mahasarkar.co.in (static fallback)")
        return unique[:20]

    except Exception as e:
        logger.error(f"Error scraping mahasarkar.co.in: {e}")
        return []


# ════════════════════════════════════════════════════════════════
# 2. RSS FEED – always included as baseline
# ════════════════════════════════════════════════════════════════

def fetch_rss_jobs_filtered():
    """
    Fetch jobs from majhinaukri.in RSS feed, filter out 'Current Affairs'
    entries, and clean HTML tags from descriptions.
    """
    feed_url = "https://majhinaukri.in/feed/"
    jobs = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:50]:
            title = entry.get('title', '').strip()
            if re.search(r'(current affairs|चालू घडामोडी)', title, re.I):
                continue

            link = entry.get('link', '#')
            raw_desc = entry.get('description', '') or entry.get('summary', '')
            if raw_desc:
                soup = BeautifulSoup(raw_desc, 'html.parser')
                description = soup.get_text(separator=' ').strip()
            else:
                description = title

            org = 'Various'
            if ':' in title:
                parts = title.split(':', 1)
                org = parts[0].strip()
                title = parts[1].strip()
            elif ' - ' in title:
                parts = title.split(' - ', 1)
                org = parts[0].strip()
                title = parts[1].strip() if len(parts) > 1 else title

            pub_date = entry.get('published', entry.get('pubDate', ''))
            last_date = None
            if pub_date:
                try:
                    from dateutil import parser as date_parser
                    last_date = date_parser.parse(pub_date).date()
                except:
                    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z'):
                        try:
                            last_date = datetime.strptime(pub_date, fmt).date()
                            break
                        except ValueError:
                            continue

            jobs.append({
                'title': title,
                'organization': org,
                'description': description[:200],
                'apply_link': link,
                'last_date': last_date,
                'source': 'rss_fallback'
            })

        logger.info(f"Filtered RSS returned {len(jobs)} job entries (excluded current affairs)")
        return jobs[:30]

    except Exception as e:
        logger.error(f"Error fetching RSS feed: {e}")
        return []


# ════════════════════════════════════════════════════════════════
# 3. MASTER FUNCTION – combines all sources
# ════════════════════════════════════════════════════════════════

def fetch_all_external_jobs():
    """
    Fetch jobs from all primary sources, plus RSS feed as a baseline.
    """
    cache_key = 'external_jobs_combined_v7'  # updated to clear old cache
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    all_jobs = []

    # Primary scrapers
    all_jobs.extend(fetch_majhinaukri_jobs())
    all_jobs.extend(fetch_majhinaukri_updates())
    all_jobs.extend(fetch_govtjobsalert_jobs())
    all_jobs.extend(fetch_indgovtjobs_jobs())
    all_jobs.extend(fetch_mahasarkar_jobs())

    # ALWAYS include RSS feed (even if primary scrapers succeed)
    rss_jobs = fetch_rss_jobs_filtered()
    all_jobs.extend(rss_jobs)

    # ---- Global deduplication ----
    def normalize_title(title):
        t = title.lower().strip()
        t = re.sub(r'\s*(bharti|recruitment|vacancy|notification|भरती|नोकरी|जागा)\s*', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    seen_titles = set()
    seen_links = set()
    unique_jobs = []

    for job in all_jobs:
        link = job.get('apply_link', '').strip()
        title = job.get('title', '').strip()
        if not title:
            continue
        norm_title = normalize_title(title)
        key = link if link and link != '#' else norm_title
        if key in seen_links or norm_title in seen_titles:
            continue
        seen_links.add(key)
        seen_titles.add(norm_title)
        unique_jobs.append(job)

    # Sort by last_date (newest first)
    unique_jobs.sort(
        key=lambda x: x.get('last_date') or datetime.min.date(),
        reverse=True
    )

    logger.info(f"Total unique jobs after deduplication: {len(unique_jobs)}")
    cache.set(cache_key, unique_jobs, 3600)
    return unique_jobs


# ────────────────────────────────────────────────────────────────
# 4. (Optional) Playwright scrapers – keep as is
# ────────────────────────────────────────────────────────────────

def fetch_mahasarkar_jobs_with_playwright():
    # ... (unchanged, you can keep the existing code)
    pass

def fetch_cscjob_jobs():
    # ... (unchanged)
    pass


# ────────────────────────────────────────────────────────────────
# 5. GOVERNMENT SCHEMES – updated with fetch_with_retry
# ────────────────────────────────────────────────────────────────

def fetch_rdd_schemes():
    schemes = []
    sources = [
        ('https://rdd.maharashtra.gov.in/en/provider/state-government/', 'state'),
        ('https://rdd.maharashtra.gov.in/en/provider/central-government/', 'central'),
        ('https://rdd.maharashtra.gov.in/en/provider/joint-venture-central-state/', 'joint'),
    ]
    for url, provider in sources:
        try:
            response = fetch_with_retry(url, timeout=25)
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('ul li a, .scheme-list a, .content a')
            for item in items:
                title = item.text.strip()
                href = item.get('href')
                if not title or len(title) < 5:
                    continue
                if any(skip in title.lower() for skip in ['home', 'contact', 'about', 'rti', 'faq']):
                    continue
                if href and not href.startswith('http'):
                    href = urljoin(url, href)
                provider_label = {
                    'state': 'State Government',
                    'central': 'Central Government',
                    'joint': 'Joint Venture (Central & State)'
                }.get(provider, 'Government')
                schemes.append({
                    'title': title,
                    'description': '',
                    'eligibility': '',
                    'last_date': None,
                    'status': 'active',
                    'provider': provider_label,
                    'department': 'Rural Development & Panchayat Raj',
                    'apply_link': href or url,
                    'official_link': href or url,
                    'source': 'rdd_maharashtra',
                    'category': 'Rural Development'
                })
            logger.info(f"Scraped {len(items)} schemes from {url}")
        except Exception as e:
            logger.error(f"Error scraping RDD schemes from {url}: {e}")
    return schemes[:50]


def fetch_mahaschemes_schemes():
    url = "https://mahaschemes.in/"
    schemes = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('article, .post, .scheme-item, .yojana-item')
        for item in items:
            title_tag = item.find('h2') or item.find('h3') or item.find('a')
            if not title_tag:
                continue
            title = title_tag.text.strip()
            if len(title) < 5:
                continue
            link_tag = item.find('a')
            href = link_tag.get('href') if link_tag else None
            desc_tag = item.find('p')
            description = desc_tag.text.strip() if desc_tag else ''
            schemes.append({
                'title': title,
                'description': description[:500] if description else '',
                'eligibility': '',
                'last_date': None,
                'status': 'active',
                'provider': 'State Government',
                'department': 'Various',
                'apply_link': href if href else url,
                'official_link': href if href else url,
                'source': 'mahaschemes',
                'category': 'Government Scheme'
            })
        logger.info(f"Scraped {len(schemes)} schemes from mahaschemes.in")
        return schemes[:30]
    except Exception as e:
        logger.error(f"Error scraping mahaschemes.in: {e}")
        return []


def fetch_plan_district_schemes():
    url = "https://plan.maharashtra.gov.in/en/36-districts/"
    schemes = []
    try:
        response = fetch_with_retry(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        districts = soup.find_all('a', href=True)
        for district in districts:
            text = district.text.strip()
            href = district.get('href')
            if text and len(text) > 3 and 'district' in href.lower():
                schemes.append({
                    'title': f"{text} District Schemes",
                    'description': f"Government schemes available in {text} district, Maharashtra.",
                    'eligibility': 'Residents of the district',
                    'last_date': None,
                    'status': 'ongoing',
                    'provider': 'State Government',
                    'department': 'Planning Department',
                    'district': text,
                    'apply_link': href if href.startswith('http') else urljoin(url, href),
                    'official_link': href if href.startswith('http') else urljoin(url, href),
                    'source': 'plan_maharashtra',
                    'category': 'District Schemes'
                })
        logger.info(f"Scraped {len(schemes)} district schemes from plan.maharashtra.gov.in")
        return schemes
    except Exception as e:
        logger.error(f"Error scraping plan.maharashtra.gov.in: {e}")
        return []


def fetch_all_external_schemes():
    cache_key = 'external_schemes_combined'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    all_schemes = []
    all_schemes.extend(fetch_rdd_schemes())
    all_schemes.extend(fetch_mahaschemes_schemes())
    all_schemes.extend(fetch_plan_district_schemes())

    def normalize_title(title):
        t = title.lower().strip()
        t = re.sub(r'\s*(scheme|yojana|योजना|पद्धत)\s*', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    seen_titles = set()
    unique_schemes = []
    for scheme in all_schemes:
        title = scheme.get('title', '').strip()
        if not title:
            continue
        norm_title = normalize_title(title)
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        unique_schemes.append(scheme)

    logger.info(f"Total unique schemes: {len(unique_schemes)} (from {len(all_schemes)} raw)")
    cache.set(cache_key, unique_schemes, 3600)
    return unique_schemes
