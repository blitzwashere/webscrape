import os
import shutil
import asyncio
from pyppeteer import launch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiohttp

# Create the "sites" folder if it doesn't exist
if not os.path.exists('sites'):
    os.makedirs('sites')


async def download_file(url, folder):
    """
    Downloads a file from the URL and saves it into the specified folder.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    filename = os.path.join(folder, os.path.basename(url))
                    with open(filename, 'wb') as file:
                        content = await response.read()
                        file.write(content)
                else:
                    print(f"Failed to download {url}: HTTP {response.status}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")


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

        # Download all linked resources (e.g., images, CSS, JS)
        for tag in soup.find_all(['a', 'img', 'link', 'script']):
            src = tag.get('href') or tag.get('src')
            if src:
                resource_url = urljoin(url, src)
                if resource_url.endswith(('.woff', '.woff2', '.ttf', '.eot')):  # Skip font files
                    print(f"Skipping font resource: {resource_url}")
                    continue
                await download_file(resource_url, folder)

        return True  # Scraping succeeded
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return False  # Scraping failed
    finally:
        await browser.close()


def main():
    website_url = input("Enter the URL of the website to scrape: ")
    # Extract domain name from URL without 'http' or 'https'
    parsed_url = urlparse(website_url)
    domain = parsed_url.netloc

    # Create a folder inside 'sites' with the domain name
    folder_name = os.path.join('sites', domain)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # Run the asyncio event loop for pyppeteer
    success = asyncio.get_event_loop().run_until_complete(scrape_website_with_pyppeteer(website_url, folder_name))

    # If scraping failed, remove the incomplete folder
    if not success:
        print(f"Removing incomplete folder: {folder_name}")
        shutil.rmtree(folder_name, ignore_errors=True)


if __name__ == "__main__":
    main()