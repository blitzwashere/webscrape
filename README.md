# Web Scraper

This project is a Python-based web scraper that downloads a website's HTML content and its linked resources (e.g., images, CSS, JS). It uses `pyppeteer` for rendering JavaScript-heavy pages and `aiohttp` for asynchronous resource downloading.

## Features
- Scrapes JavaScript-rendered websites.
- Downloads linked resources concurrently.
- Handles common HTTP errors gracefully.

## Setup
1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd webscrape