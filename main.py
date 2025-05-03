import os
import shutil
import asyncio
from pyppeteer import launch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the "sites" folder if it doesn't exist
if not os.path.exists('sites'):
    os.makedirs('sites')


async def download_file(url, folder):
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
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        filename = os.path.join(folder, os.path.basename(url))
                        if os.path.isdir(filename):
                            logger.warning(f"Skipping directory: {filename}")
                            return
                        with open(filename, 'wb') as file:
                            content = await response.read()
                            file.write(content)
                        logger.info(f"Downloaded: {url}")
                        return
                    elif response.status == 429:
                        logger.warning(f"Rate limit hit for {url}. Retrying after delay...")
                        await asyncio.sleep(backoff ** attempt)  # Exponential backoff
                    elif response.status in {403, 404}:
                        logger.warning(f"Failed to download {url}: HTTP {response.status}")
                        return
                    else:
                        logger.error(f"Unexpected HTTP error {response.status} for {url}")
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
        await asyncio.sleep(backoff ** attempt)  # Exponential backoff
    logger.error(f"Failed to download {url} after {retries} attempts.")


async def download_resources(resource_urls, folder):
    """
    Downloads multiple resources concurrently.
    """
    tasks = [download_file(url, folder) for url in resource_urls]
    await asyncio.gather(*tasks)


async def scrape_website_with_pyppeteer(url, folder):
    """
    Scrapes a website using pyppeteer and saves its content into the specified folder.
    """
    browser = await launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    page = await browser.newPage()
    try:
        await page.goto(url, timeout=30000)  # Wait for 30 seconds to load the page

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
                if resource_url.endswith(('.woff', '.woff2', '.ttf', '.eot', '.svg', '.gif')):  # Skip font and unnecessary files
                    logger.info(f"Skipping resource: {resource_url}")
                    continue
                resource_urls.append(resource_url)

        # Download all resources concurrently
        await download_resources(resource_urls, folder)

        await asyncio.sleep(5)  # Delay to avoid rate limiting

        return True  # Scraping succeeded
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return False  # Scraping failed
    finally:
        await browser.close()


def main():
    website_url = input("Enter the URL of the website to scrape: ")
    parsed_url = urlparse(website_url)
    domain = parsed_url.netloc

    folder_name = os.path.join('sites', domain)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    try:
        asyncio.run(scrape_website_with_pyppeteer(website_url, folder_name))
    except Exception as e:
        print(f"An error occurred: {e}")
        shutil.rmtree(folder_name, ignore_errors=True)


if __name__ == "__main__":
    main()