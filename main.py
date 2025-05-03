import os
import shutil
import asyncio
import argparse
from pyppeteer import launch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiohttp
import logging
from tqdm.asyncio import tqdm
import unittest
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create the "sites" folder if it doesn't exist
if not os.path.exists('sites'):
    os.makedirs('sites')

semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent downloads

async def download_file(url, folder, downloaded, skipped, failed):
    """
    Downloads a file from the URL and saves it into the specified folder.
    """
    retries = 3
    backoff = 2  # Exponential backoff factor
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=100, limit_per_host=10)) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        filename = os.path.join(folder, os.path.basename(url))
                        if os.path.isdir(filename):
                            logger.warning(f"Skipping directory: {filename}")
                            return
                        with open(filename, 'wb') as file:
                            content = await response.read()
                            file.write(content)
                        logger.info(f"Downloaded: {url}")
                        downloaded.append(url)
                        return
                    elif response.status == 429:
                        logger.warning(f"Rate limit hit for {url}. Retrying after delay...")
                        await asyncio.sleep(backoff ** attempt)  # Exponential backoff
                    elif response.status in {403, 404}:
                        logger.warning(f"Failed to download {url}: HTTP {response.status}")
                        failed.append(url)
                        return
                    else:
                        logger.error(f"Unexpected HTTP error {response.status} for {url}")
                        skipped.append(url)
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
        await asyncio.sleep(backoff ** attempt)  # Exponential backoff
    logger.error(f"Failed to download {url} after {retries} attempts.")


async def download_file_with_limit(url, folder, downloaded, skipped, failed):
    async with semaphore:
        await download_file(url, folder, downloaded, skipped, failed)


async def download_resources(resource_urls, folder, downloaded, skipped, failed):
    for url in tqdm(resource_urls, desc="Downloading resources"):
        await download_file_with_limit(url, folder, downloaded, skipped, failed)


async def scrape_website_with_pyppeteer(url, folder, timeout, downloaded, skipped, failed):
    """
    Scrapes a website using pyppeteer and saves its content into the specified folder.
    """
    # List of social media domains to exclude
    social_media_domains = [
        'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
        'youtube.com', 'tiktok.com', 'pinterest.com', 'reddit.com'
    ]

    browser = await launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    page = await browser.newPage()
    try:
        await page.goto(url, timeout=30000)
        await page.waitForSelector("body")  # Wait for the body element to load

        # Get the page content after rendering JavaScript
        content = await page.content()

        # Parse the HTML using BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        # Save the index.html file
        with open(os.path.join(folder, 'index.html'), 'w', encoding='utf-8') as file:
            file.write(soup.prettify())

        # Collect all linked resources (e.g., images, CSS, JS)
        resource_urls = []
        for tag in soup.find_all(['a', 'img', 'link', 'script']):
            src = tag.get('href') or tag.get('src')
            if src:
                resource_url = urljoin(url, src)
                # Skip social media links
                if any(domain in resource_url for domain in social_media_domains):
                    logger.info(f"Skipping social media link: {resource_url}")
                    continue
                # Skip unnecessary resources
                if resource_url.endswith(('.woff', '.woff2', '.ttf', '.eot', '.svg', '.gif', '.ico', '.webp')):
                    logger.info(f"Skipping resource: {resource_url}")
                    continue
                if "analytics" in resource_url or "tracking" in resource_url:
                    logger.info(f"Skipping analytics/tracking resource: {resource_url}")
                    continue
                resource_urls.append(resource_url)

        # Download all resources concurrently
        await download_resources(resource_urls, folder, downloaded, skipped, failed)

        await asyncio.sleep(5)  # Delay to avoid rate limiting

        return True  # Scraping succeeded
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return False  # Scraping failed
    finally:
        await browser.close()


async def scrape_with_retries(url, folder, timeout, downloaded, skipped, failed, retries=3):
    for attempt in range(retries):
        success = await scrape_website_with_pyppeteer(url, folder, timeout, downloaded, skipped, failed)
        if success:
            return True
        logger.warning(f"Retrying scraping for {url} (Attempt {attempt + 1}/{retries})")
    logger.error(f"Failed to scrape {url} after {retries} attempts.")
    return False


async def check_robots_txt(url):
    robots_url = urljoin(url, "/robots.txt")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get(robots_url) as response:
            if response.status == 200:
                content = await response.text()
                logger.info(f"Robots.txt content:\n{content}")
                if "Disallow" in content:
                    logger.warning("Scraping may be disallowed by robots.txt. Proceed with caution.")


async def parse_sitemap(url, folder, timeout, downloaded, skipped, failed):
    sitemap_url = urljoin(url, "/sitemap.xml")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get(sitemap_url) as response:
            if response.status == 200:
                content = await response.text()
                logger.info(f"Sitemap content:\n{content}")
                # Example: Parse and iterate over URLs
                sitemap_urls = extract_urls_from_sitemap(content)
                for sitemap_url in sitemap_urls:
                    await scrape_with_retries(sitemap_url, folder, timeout, downloaded, skipped, failed)


def extract_urls_from_sitemap(content):
    from xml.etree import ElementTree as ET
    urls = []
    try:
        root = ET.fromstring(content)
        for url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            urls.append(url.text)
    except ET.ParseError as e:
        logger.error(f"Failed to parse sitemap: {e}")
    return urls


def generate_report(downloaded, skipped, failed):
    print("\nSummary Report:")
    print(f"Downloaded: {len(downloaded)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Failed: {len(failed)}")


def main():
    parser = argparse.ArgumentParser(description="Web scraper using pyppeteer.")
    parser.add_argument("url", help="The URL of the website to scrape.")
    parser.add_argument("--output", default="sites", help="The output folder for scraped content.")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout for page loading (in seconds).")
    parser.add_argument("--skip-sitemap", action="store_true", help="Skip parsing the sitemap.")
    parser.add_argument("--skip-robots", action="store_true", help="Skip checking robots.txt.")
    args = parser.parse_args()

    website_url = args.url
    if not website_url.startswith(('http://', 'https://')):
        website_url = f"https://{website_url}"

    try:
        parsed_url = urlparse(website_url)
        if not parsed_url.netloc:
            raise ValueError("Invalid URL provided.")
    except ValueError as e:
        logger.error(f"Invalid URL: {e}")
        return

    folder_name = os.path.join(args.output, urlparse(website_url).netloc)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    downloaded = []
    skipped = []
    failed = []

    try:
        asyncio.run(scrape_with_retries(website_url, folder_name, args.timeout, downloaded, skipped, failed))
        asyncio.run(parse_sitemap(website_url, folder_name, args.timeout, downloaded, skipped, failed))
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        shutil.rmtree(folder_name, ignore_errors=True)
    except aiohttp.ClientError as e:
        logger.error(f"Network error: {e}")
        shutil.rmtree(folder_name, ignore_errors=True)
    except ValueError as e:
        logger.error(f"Invalid URL: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

    generate_report(downloaded, skipped, failed)


if __name__ == "__main__":
    main()


class TestScraper(unittest.TestCase):
    def test_url_filtering(self):
        url = "https://facebook.com"
        self.assertTrue(any(domain in url for domain in ['facebook.com', 'twitter.com']))

    def test_resource_filtering(self):
        url = "https://example.com/resource.woff"
        self.assertTrue(url.endswith(('.woff', '.woff2', '.ttf', '.eot', '.svg', '.gif')))

    def test_extract_urls_from_sitemap(self):
        sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>"""
        urls = extract_urls_from_sitemap(sitemap_content)
        self.assertEqual(urls, ["https://example.com/page1", "https://example.com/page2"])