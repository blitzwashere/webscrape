import os
import shutil
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Create the "sites" folder if it doesn't exist
if not os.path.exists('sites'):
    os.makedirs('sites')

def get_proxies_from_url(proxies_url):
    """
    Fetches proxies from the given URL and returns a list of proxies.
    """
    try:
        response = requests.get(proxies_url, timeout=10)
        response.raise_for_status()
        return response.text.splitlines()
    except Exception as e:
        print(f"Failed to fetch proxies from {proxies_url}: {e}")
        return []

def download_file(url, folder, proxies=None):
    """
    Downloads a file from the URL and saves it into the specified folder.
    """
    try:
        response = requests.get(url, proxies=proxies, timeout=10)
        if response.status_code == 404:
            print(f"Resource not found: {url}")
            return
        elif response.status_code == 500:
            print(f"Server error for resource: {url}")
            return

        response.raise_for_status()
        filename = os.path.join(folder, os.path.basename(url))
        with open(filename, 'wb') as file:
            file.write(response.content)
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def scrape_website(url, folder, proxies=None):
    """
    Scrapes the website URL and saves its content into the specified folder.
    """
    try:
        response = requests.get(url, proxies=proxies, timeout=10)
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
                # Skip non-essential resources
                if resource_url.endswith(('.woff', '.woff2', '.ttf', '.eot')):  # Fonts
                    print(f"Skipping font resource: {resource_url}")
                    continue
                download_file(resource_url, folder, proxies)

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

    # URL to fetch free proxies
    proxies_url = "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt"
    proxies_list = get_proxies_from_url(proxies_url)

    if not proxies_list:
        print("No proxies available. Exiting.")
        return

    # Attempt to scrape the website with each proxy
    success = False
    for proxy in proxies_list:
        proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'  # Use HTTP proxy for HTTPS requests
        }

        print(f"Trying proxy: {proxy}")
        success = scrape_website(website_url, folder_name, proxies)

        if success:
            print(f"Successfully scraped {website_url} using proxy {proxy}")
            break
        else:
            print(f"Proxy {proxy} failed. Trying the next one...")

    # If scraping failed with all proxies, remove the incomplete folder
    if not success:
        print(f"Removing incomplete folder: {folder_name}")
        shutil.rmtree(folder_name, ignore_errors=True)

if __name__ == "__main__":
    main()