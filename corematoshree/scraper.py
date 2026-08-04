import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from datetime import timedelta
from django.core.cache import cache
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# ============================================================
# 1. MAJHI NAUKRI (already working)
# ============================================================

def fetch_majhinaukri_jobs():
    """
    Scrape genuine job listings from majhinaukri.in homepage.
    Filters out headings, utilities, and extracts last date if available.
    """
    url = "https://majhinaukri.in/"
    jobs = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Blacklist for headings / non-job links ---
        HEADING_BLACKLIST = {
            "वर्तमान भरती", "latest jobs", "view more", "prev", "next",
            "«", "»", "←", "→", "previous", "next page",
            "नवीनतम भरती", "ताज्या भरती", "नोकरीच्या जाहिराती",
            "popular departments", "government jobs", "private jobs"
        }

        # --- Job keywords (English + Marathi) ---
        JOB_KEYWORDS = {
            "bharti", "recruitment", "job", "vacancy", "notification",
            "भरती", "मेळावा", "नोकरी", "पद", "जागा", "नियुक्ति",
            "walk-in", "apply", "exam", "admit card", "result"
        }

        # --- Find all anchor tags ---
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.text.strip()
            text_lower = text.lower()

            # 1. Must be a full URL under majhinaukri.in
            if not href.startswith('https://majhinaukri.in/'):
                continue

            # 2. Skip obvious non-job paths
            if any(skip in href for skip in ['/category/', '/tag/', '/page/', '/wp-', '#', '?page=']):
                continue

            # 3. Skip if title is in heading blacklist (exact match or contains phrase)
            if any(phrase in text_lower for phrase in HEADING_BLACKLIST):
                continue

            # 4. Skip purely numeric pagination (e.g., "1", "2", "3")
            if text.isdigit():
                continue

            # 5. Skip if text is "Prev" or "Next" (case-insensitive)
            if text_lower in ("prev", "next"):
                continue

            # 6. Skip if text contains "View More" (case-insensitive)
            if "view more" in text_lower:
                continue

            # 7. Skip if title is too short (less than 5 characters)
            if len(text) < 5:
                continue

            # 8. Strong filter: check for date pattern in URL (e.g., /2026/08/) OR job keyword in title
            has_date = re.search(r'/\d{4}/\d{2}/\d{2}/', href) is not None
            has_keyword = any(kw in text_lower for kw in JOB_KEYWORDS)
            if not (has_date or has_keyword):
                continue

            # --- Clean up the title ---
            # Remove common prefixes like "Latest Jobs:", "वर्तमान भरती" etc.
            clean_title = text
            for prefix in ["latest jobs:", "वर्तमान भरती:", "ताज्या भरती:", "नवीनतम भरती:"]:
                if clean_title.lower().startswith(prefix):
                    clean_title = clean_title[len(prefix):].strip()
                    break

            # --- Extract last date from the surrounding element ---
            last_date = None
            # Check if the anchor has a parent with text containing date
            parent = a.parent
            if parent:
                parent_text = parent.get_text()
                # Look for patterns like "2 days ago", "2d ago", "2d", "2 days"
                date_match = re.search(r'(\d+)\s*(day|d|days?)\s*ago', parent_text, re.I)
                if date_match:
                    days_ago = int(date_match.group(1))
                    last_date = datetime.now().date() - timedelta(days=days_ago)
                else:
                    # Try exact date format "DD MMM YYYY" or "DD-MM-YYYY"
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

        # --- Deduplicate by link ---
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job['apply_link'] not in seen:
                seen.add(job['apply_link'])
                unique_jobs.append(job)

        logger.info(f"Scraped {len(unique_jobs)} jobs from majhinaukri.in")
        return unique_jobs[:30]

    except Exception as e:
        logger.error(f"Error scraping majhinaukri.in: {e}")
        return []


# ============================================================
# 2. GOVT JOBS ALERT (Maharashtra page)
# ============================================================

def fetch_govtjobsalert_jobs():
    """
    Scrape job listings from govtjobsalert.in Maharashtra page using BeautifulSoup + regex fallback.
    """
    url = "https://govtjobsalert.in/maharashtra-govt-jobs/"
    jobs = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try common selectors
        items = soup.select('article')
        if not items:
            items = soup.select('.job-list, .post, .entry-content ul li')

        for item in items:
            link_tag = item.find('a')
            if not link_tag:
                continue
            title = link_tag.text.strip()
            href = link_tag.get('href')
            if not href:
                continue
            if not href.startswith('http'):
                href = 'https://govtjobsalert.in' + href
            if len(title) < 5:
                continue

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

        # Fallback regex if no jobs found
        if not jobs:
            html = response.text
            pattern = r'Job Post[^\]]*?Last Date:\s*(\d{2}\s+[A-Za-z]{3}\s+\d{4})[^#]*###\s*([^)]+)\(([^)]+)\)'
            matches = re.findall(pattern, html)
            for last_date_str, title, link in matches:
                title = title.strip()
                title = re.sub(r'^\[.*?\]\s*', '', title)
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

        # Deduplicate
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


# ============================================================
# 3. MH INDGOVTJOBS.NET (New – table-based)
# ============================================================

def fetch_indgovtjobs_jobs():
    """
    Scrape job listings from mh.indgovtjobs.net.
    Jobs are in a table format.
    """
    url = "https://mh.indgovtjobs.net/"
    jobs = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        rows = soup.select('table tr')
        for row in rows:
            links = row.find_all('a')
            if not links:
                continue
            job_link = links[0]
            title = job_link.text.strip()
            href = job_link.get('href')
            if not href:
                continue
            if not href.startswith('http'):
                href = urljoin(url, href)
            if len(title) < 5:
                continue

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

            description_parts = []
            if vacancies:
                description_parts.append(f"Vacancies: {vacancies}")
            if last_date:
                description_parts.append(f"Last Date: {last_date.strftime('%d %b %Y')}")
            description = " | ".join(description_parts)

            jobs.append({
                'title': title,
                'organization': 'MH IndGovtJobs',
                'description': description,
                'apply_link': href,
                'last_date': last_date,
                'source': 'indgovtjobs'
            })

        # Fallback if no table rows found
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

        # Deduplicate
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


# ============================================================
# 4. MAHASARKAR.CO.IN (Static fallback – limited)
# ============================================================

def fetch_mahasarkar_jobs():
    """
    Scrape job listings from mahasarkar.co.in using static HTML.
    ⚠️ This site uses client-side rendering, so this returns minimal results.
    For full data, use fetch_mahasarkar_jobs_with_playwright().
    """
    url = "https://mahasarkar.co.in/"
    jobs = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract from script tags (Next.js initial state)
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
            logger.warning("mahasarkar.co.in: No jobs found in static HTML. Consider using Playwright.")

        # Deduplicate
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


# ============================================================
# 5. MAHASARKAR WITH PLAYWRIGHT (Full JS rendering)
# ============================================================

def fetch_mahasarkar_jobs_with_playwright():
    """
    🚀 Use Playwright to scrape client-side rendered jobs from mahasarkar.co.in.
    Requires: pip install playwright && playwright install
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install")
        return []

    jobs = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://mahasarkar.co.in/", timeout=30000)
            page.wait_for_selector("a[href*='bharti']", timeout=10000)
            links = page.query_selector_all("a[href*='bharti'], a[href*='recruitment']")
            for link in links[:30]:
                title = link.text_content().strip()
                href = link.get_attribute('href')
                if href and not href.startswith('http'):
                    href = "https://mahasarkar.co.in" + href
                if title and len(title) > 5:
                    jobs.append({
                        'title': title,
                        'organization': 'Mahasarkar',
                        'description': '',
                        'apply_link': href,
                        'last_date': None,
                        'source': 'mahasarkar'
                    })
            browser.close()

        # Deduplicate
        seen = set()
        unique = []
        for job in jobs:
            if job['apply_link'] not in seen:
                seen.add(job['apply_link'])
                unique.append(job)

        logger.info(f"Scraped {len(unique)} jobs from mahasarkar.co.in (Playwright)")
        return unique[:30]

    except Exception as e:
        logger.error(f"Playwright scraping failed for mahasarkar.co.in: {e}")
        return []


# ============================================================
# 6. MASTER FUNCTION – Combine & Deduplicate
# ============================================================

def fetch_all_external_jobs():
    """
    Fetch jobs from ALL external sources and combine them with global deduplication.
    """
    cache_key = 'external_jobs_combined_v2'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    all_jobs = []

    # 1. Existing sources
    all_jobs.extend(fetch_majhinaukri_jobs())
    all_jobs.extend(fetch_govtjobsalert_jobs())

    # 2. New sources
    all_jobs.extend(fetch_indgovtjobs_jobs())
    all_jobs.extend(fetch_mahasarkar_jobs())          # static fallback (limited)
    # all_jobs.extend(fetch_mahasarkar_jobs_with_playwright())  # ← uncomment for full scraping

    # ============================================================
    # GLOBAL DEDUPLICATION – removes duplicates across all sources
    # ============================================================
    
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
        if not link or link == '#':
            continue
        norm_title = normalize_title(title)
        if link in seen_links or norm_title in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(norm_title)
        unique_jobs.append(job)

    unique_jobs.sort(
        key=lambda x: x.get('last_date') or datetime.min.date(),
        reverse=True
    )

    logger.info(f"Total unique jobs after deduplication: {len(unique_jobs)} (from {len(all_jobs)} raw)")

    cache.set(cache_key, unique_jobs, 3600)
    return unique_jobs

def fetch_cscjob_jobs():
    """
    Scrape job listings from nandurbar1.cscjob.com using Playwright.
    Requires: pip install playwright && playwright install
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install")
        return []

    jobs = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://nandurbar1.cscjob.com/jobs", timeout=30000)
            
            # Wait for job content to load
            page.wait_for_selector("text=भरती", timeout=10000)
            
            # Get all job links/items
            # You'll need to inspect the page to find the correct selector
            # Based on visible content, jobs appear as list items with dates
            job_elements = page.query_selector_all("a[href*='job']")
            
            for element in job_elements[:30]:
                title = element.text_content().strip()
                href = element.get_attribute('href')
                if href and not href.startswith('http'):
                    href = "https://nandurbar1.cscjob.com" + href
                if title and len(title) > 10:
                    # Extract date if present (format: "24 Aug, 2026")
                    date_match = re.search(r'(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})', title)
                    last_date = None
                    if date_match:
                        try:
                            last_date = datetime.strptime(date_match.group(1), '%d %b, %Y').date()
                        except:
                            pass
                    
                    # Extract organization from title
                    org = "CSC Job"
                    # Look for patterns like "PNB LBO" or "KONKAN RAILWAY" at start
                    org_match = re.match(r'^([A-Z\s]+)\s*[\(（]', title)
                    if org_match:
                        org = org_match.group(1).strip()
                    
                    jobs.append({
                        'title': title,
                        'organization': org,
                        'description': '',
                        'apply_link': href,
                        'last_date': last_date,
                        'source': 'cscjob'
                    })
            
            browser.close()
            
        # Deduplicate
        seen = set()
        unique = []
        for job in jobs:
            if job['apply_link'] not in seen:
                seen.add(job['apply_link'])
                unique.append(job)
        
        logger.info(f"Scraped {len(unique)} jobs from nandurbar1.cscjob.com")
        return unique[:30]
        
    except Exception as e:
        logger.error(f"Playwright scraping failed for nandurbar1.cscjob.com: {e}")
        return []
    
# ============================================================
# GOVERNMENT SCHEMES SCRAPER – Maharashtra Focus
# ============================================================

def fetch_rdd_schemes():
    """
    Scrape schemes from Rural Development Department, Maharashtra.
    Sources: State, Central, and Joint Venture schemes.
    """
    schemes = []
    sources = [
        ('https://rdd.maharashtra.gov.in/en/provider/state-government/', 'state'),
        ('https://rdd.maharashtra.gov.in/en/provider/central-government/', 'central'),
        ('https://rdd.maharashtra.gov.in/en/provider/joint-venture-central-state/', 'joint'),
    ]
    
    for url, provider in sources:
        try:
            response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find scheme listings – adjust selectors based on actual HTML
            # Look for list items or divs containing scheme info
            items = soup.select('ul li a, .scheme-list a, .content a')
            
            for item in items:
                title = item.text.strip()
                href = item.get('href')
                if not title or len(title) < 5:
                    continue
                # Skip navigation links
                if any(skip in title.lower() for skip in ['home', 'contact', 'about', 'rti', 'faq']):
                    continue
                    
                # Build full URL
                if href and not href.startswith('http'):
                    href = urljoin(url, href)
                
                # Determine provider label
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
    
    return schemes[:50]  # Limit to avoid duplicates


def fetch_mahaschemes_schemes():
    """
    Scrape schemes from MahaSchemes.in – aggregator for Maharashtra schemes.
    """
    url = "https://mahaschemes.in/"
    schemes = []
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for scheme cards or list items
        # The site has categories; we'll extract what's visible
        items = soup.select('article, .post, .scheme-item, .yojana-item')
        
        for item in items:
            # Find title
            title_tag = item.find('h2') or item.find('h3') or item.find('a')
            if not title_tag:
                continue
            title = title_tag.text.strip()
            if len(title) < 5:
                continue
            
            # Find link
            link_tag = item.find('a')
            href = link_tag.get('href') if link_tag else None
            
            # Find description
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
    """
    Scrape district-wise schemes from Planning Department.
    """
    url = "https://plan.maharashtra.gov.in/en/36-districts/"
    schemes = []
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract district names
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
    """
    Fetch schemes from ALL external sources and combine with deduplication.
    """
    cache_key = 'external_schemes_combined'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    all_schemes = []
    
    # 1. RDD Schemes (State, Central, Joint)
    all_schemes.extend(fetch_rdd_schemes())
    
    # 2. MahaSchemes
    all_schemes.extend(fetch_mahaschemes_schemes())
    
    # 3. District Schemes
    all_schemes.extend(fetch_plan_district_schemes())
    
    # ============================================================
    # DEDUPLICATION – remove duplicates by title
    # ============================================================
    
    def normalize_title(title):
        t = title.lower().strip()
        # Remove common prefixes/suffixes
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
    
    cache.set(cache_key, unique_schemes, 3600)  # Cache for 1 hour
    return unique_schemes

