import os
import shutil
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Create the "sites" folder if it doesn't exist
if not os.path.exists('sites'):
    os.makedirs('sites')

SCRAPINGBEE_API_KEY = "X5UJ6XDGAPZB1FQNFFV7Y8K4ULIBBDC6YDVSYWQSIEEPS4GE0X7FMT8PIFHUXVITVF6CUOALJRDUJGOH"  # Replace with your ScrapingBee API key

def download_file_with_scrapingbee(url, folder):
    """
    Downloads a file using ScrapingBee API and saves it into the specified folder.
    """
    try:
        response = requests.get(
            "https://app.scrapingbee.com/api/v1/",
            params={
                "api_key": SCRAPINGBEE_API_KEY,
                "url": url,
            },
            timeout=10,
        )
        response.raise_for_status()
        filename = os.path.join(folder, os.path.basename(url))
        with open(filename, 'wb') as file:
            file.write(response.content)
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def scrape_website_with_scrapingbee(url, folder):
    """
    Scrapes the website URL using ScrapingBee API and saves its content into the specified folder.
    """
    try:
        response = requests.get(
            "https://app.scrapingbee.com/api/v1/",
            params={
                "api_key": SCRAPINGBEE_API_KEY,
                "url": url,
            },
            timeout=10,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Save the index.html file
        with open(os.path.join(folder, 'index.html'), 'w', encoding='utf-8') as file:
            file.write(soup.prettify())

        # Download all linked resources (e.g., images, CSS, JS)
        for tag in soup.find_all(['a', 'img', 'link', 'script']):
            src = tag.get('href') or tag.get('src')
            if src:
                resource_url = urljoin(url, src)
                download_file_with_scrapingbee(resource_url, folder)

        return True  # Scraping succeeded
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return False  # Scraping failed

def main():
    website_url = input("Enter the URL of the website to scrape: ")
    # Extract domain name from URL without 'http' or 'https'
    parsed_url = urlparse(website_url)
    domain = parsed_url.netloc

    # Create a folder inside 'sites' with the domain name
    folder_name = os.path.join('sites', domain)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # Attempt to scrape the website using ScrapingBee
    success = scrape_website_with_scrapingbee(website_url, folder_name)

    # If scraping failed, remove the incomplete folder
    if not success:
        print(f"Removing incomplete folder: {folder_name}")
        shutil.rmtree(folder_name, ignore_errors=True)

if __name__ == "__main__":
    main()