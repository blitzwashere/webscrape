import os
import shutil
import asyncio
from pyppeteer import launch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import aiohttp
from jsbeautifier import beautify
import base64

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


def unobfuscate_file(file_path):
    """
    Unobfuscates a file if it is minified or encoded.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Example 1: Unobfuscate minified JavaScript or CSS
        if file_path.endswith('.js') or file_path.endswith('.css'):
            unobfuscated_content = beautify(content)
        
        # Example 2: Decode Base64-encoded files
        elif content.strip().startswith("data:"):
            # Extract and decode the Base64 portion
            base64_data = content.split(",")[1]
            unobfuscated_content = base64.b64decode(base64_data).decode('utf-8')
        
        # Example 3: Handle custom obfuscation cases
        # Add logic here for other obfuscation methods...

        else:
            print(f"No unobfuscation logic for file type: {file_path}")
            return

        # Save the unobfuscated content back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(unobfuscated_content)

        print(f"Unobfuscated file: {file_path}")

    except Exception as e:
        print(f"Failed to unobfuscate {file_path}: {e}")


async def scrape_website_with_pyppeteer_and_unobfuscate(url, folder):
    """
    Scrapes a website using pyppeteer, downloads its resources, and unobfuscates files if needed.
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
        index_path = os.path.join(folder, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as file:
            file.write(soup.prettify())

        # Download all linked resources (e.g., images, CSS, JS)
        for tag in soup.find_all(['a', 'img', 'link', 'script']):
            src = tag.get('href') or tag.get('src')
            if src:
                resource_url = urljoin(url, src)
                file_path = os.path.join(folder, os.path.basename(resource_url))

                # Skip font files
                if resource_url.endswith(('.woff', '.woff2', '.ttf', '.eot')):
                    print(f"Skipping font resource: {resource_url}")
                    continue

                await download_file(resource_url, folder)

                # Attempt to unobfuscate the file
                unobfuscate_file(file_path)

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
    success = asyncio.get_event_loop().run_until_complete(
        scrape_website_with_pyppeteer_and_unobfuscate(website_url, folder_name)
    )

    # If scraping failed, remove the incomplete folder
    if not success:
        print(f"Removing incomplete folder: {folder_name}")
        shutil.rmtree(folder_name, ignore_errors=True)


if __name__ == "__main__":
    main()