import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Create the "sites" folder if it doesn't exist
if not os.path.exists('sites'):
    os.makedirs('sites')

def download_file(url, folder, proxies=None):
    try:
        response = requests.get(url, proxies=proxies, timeout=10)
        response.raise_for_status()
        filename = os.path.join(folder, os.path.basename(url))
        with open(filename, 'wb') as file:
            file.write(response.content)
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def scrape_website(url, folder, proxies=None):
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
                download_file(resource_url, folder, proxies)
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")

def main():
    website_url = input("Enter the URL of the website to scrape: ")
    # Extract domain name from URL without 'http' or 'https'
    parsed_url = urlparse(website_url)
    domain = parsed_url.netloc

    # Create a folder inside 'sites' with the domain name
    folder_name = os.path.join('sites', domain)
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # Use proxies from proxies.txt
    proxies = {}
    if os.path.exists('proxies.txt'):
        with open('proxies.txt', 'r') as proxy_file:
            proxy_list = proxy_file.readlines()
            if proxy_list:
                # Example: Use the first proxy in the list
                proxy = proxy_list[0].strip()
                proxies = {
                    'http': f'http://{proxy}',
                    'https': f'https://{proxy}',
                }

    scrape_website(website_url, folder_name, proxies)

if __name__ == "__main__":
    main()