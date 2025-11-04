import requests
import os
import csv
import re
import time
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def fetch_html(url):
    """
    Fetch HTML content from a given URL.
    
    Args:
        url (str): The URL to fetch HTML from
        
    Returns:
        str: The HTML content of the page
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None

def get_filter_options(driver):
    """
    Extract all filter categories and their options from the page.
    
    Returns:
        dict: Dictionary with category names as keys and lists of option texts as values
    """
    filters = {}
    
    # Find all parameter sections
    sections = driver.find_elements(By.CSS_SELECTOR, "section.parameter.group")
    
    for section in sections:
        # Get the category name
        question = section.find_element(By.CSS_SELECTOR, "div.question").text
        
        # Get all option buttons
        buttons = section.find_elements(By.CSS_SELECTOR, "div.buttons button")
        options = [btn.find_element(By.CSS_SELECTOR, "div.option").text for btn in buttons]
        
        filters[question] = {
            'options': options,
            'buttons': buttons
        }
    
    return filters

def extract_graph_data(driver):
    """
    Extract the current graph data from the SVG.
    
    Returns:
        dict: Dictionary with party names and their values
    """
    data = {}
    
    # Wait for SVG to be present
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Byt sortering'] svg"))
        )
    except:
        return data
    
    # Get the page source and parse it
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the SVG button
    button = soup.find('button', {'aria-label': 'Byt sortering'})
    if not button:
        return data
    
    # Find the main SVG container
    svg = button.find('svg')
    if not svg:
        return data
    
    # Get all top-level g elements
    top_groups = svg.find_all('g', recursive=False)
    if len(top_groups) < 2:
        return data
    
    # The second g contains all the party data
    party_container = top_groups[1]
    party_groups = party_container.find_all('g', recursive=False)
    
    # Process pairs of groups (value group + party name group)
    i = 0
    while i < len(party_groups) - 1:
        # First group should have the percentage value
        value_group = party_groups[i]
        # Second group should have the party name
        name_group = party_groups[i + 1]
        
        # Extract value from first group
        value_texts = value_group.find_all('text')
        value = None
        for text in value_texts:
            text_content = text.get_text(strip=True)
            # The value text has specific attributes
            if text.get('dy') == '-0.33em' and text.get('font-weight') == 'bold':
                value = text_content
                break
        
        # Extract party name from second group
        party_texts = name_group.find_all('text')
        party = None
        for text in party_texts:
            text_content = text.get_text(strip=True)
            # The party name text has font-weight="900"
            if text.get('font-weight') == '900':
                party = text_content
                break
        
        # Store if both found
        if party and value:
            data[party] = value
        
        # Move to next pair
        i += 2
    
    return data

def collect_all_combinations(url, output_dir, max_combinations=None):
    """
    Collect graph data for all filter combinations.
    
    Args:
        url: The URL to scrape
        output_dir: Path object for output directory
        max_combinations: Maximum number of combinations to process (None for all)
    
    Returns:
        list: List of dictionaries with filter settings and graph data
    """
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    
    driver = None
    all_data = []
    csv_file = output_dir / "csv.csv"
    csv_initialized = False
    
    try:
        print("Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=chrome_options)
        print("[OK] Chrome WebDriver initialized successfully")
        
        print(f"Loading page: {url}")
        driver.get(url)
        print("[OK] Page loaded, waiting for JavaScript to render...")
        
        # Wait for page to load
        time.sleep(5)
        print("[OK] Page rendering complete")
        
        # Get all filter options
        print("\nExtracting filter options...")
        filters = get_filter_options(driver)
        print(f"[OK] Found {len(filters)} filter categories")
        
        # Print filter structure
        for category, info in filters.items():
            print(f"  - {category}: {len(info['options'])} options")
        
        # Calculate total combinations
        total = 1
        for info in filters.values():
            total *= len(info['options'])
        total_rows = total * 9  # 9 parties per combination
        print(f"\n[INFO] Total filter combinations: {total:,}")
        print(f"[INFO] Total CSV rows to generate: {total_rows:,} ({total:,} combinations x 9 parties)")
        
        # Define column order - now with Parti and Procent instead of party columns
        filter_columns = ['Kön', 'Ålder', 'Yrke', 'Region', 'Boende', 'Utbildning', 'Fack']
        all_columns = filter_columns + ['Parti', 'Procent']
        
        # Iterate through all combinations
        categories = list(filters.keys())
        
        def iterate_combinations(category_index, current_selection):
            nonlocal all_data, csv_initialized
            
            # Stop if we've reached the max combinations limit
            if max_combinations and len(all_data) >= max_combinations * 9:
                return
            
            if category_index >= len(categories):
                # Extract data for this combination
                graph_data = extract_graph_data(driver)
                
                # Create one row per party
                mode = 'a' if csv_initialized else 'w'
                with open(csv_file, mode, newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=all_columns, delimiter=';', quoting=csv.QUOTE_NONE, escapechar='\\')
                    if not csv_initialized:
                        writer.writeheader()
                        csv_initialized = True
                    
                    # Write a row for each party
                    for party, value in graph_data.items():
                        result = current_selection.copy()
                        result['Parti'] = party
                        result['Procent'] = value
                        writer.writerow(result)
                        all_data.append(result)
                
                if len(all_data) % 100 == 0:
                    combinations_done = len(all_data) // 9
                    percent = (len(all_data) / total_rows) * 100 if total_rows > 0 else 0
                    print(f"Progress: {len(all_data):,} rows ({combinations_done:,} combinations) - {percent:.1f}% complete")
                
                return
            
            category = categories[category_index]
            buttons = filters[category]['buttons']
            options = filters[category]['options']
            
            for i, (button, option) in enumerate(zip(buttons, options)):
                # Click the button
                try:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(0.3)  # Small delay for graph to update
                except:
                    pass
                
                # Recurse to next category
                new_selection = current_selection.copy()
                new_selection[category] = option
                iterate_combinations(category_index + 1, new_selection)
        
        # Start iteration
        print("\n" + "="*60)
        print("Starting data collection...")
        print("="*60)
        start_time = time.time()
        iterate_combinations(0, {})
        elapsed = time.time() - start_time
        
        print("\n" + "="*60)
        print(f"[DONE] Completed! Collected {len(all_data):,} rows")
        print(f"[DONE] Time elapsed: {elapsed/60:.1f} minutes")
        print("="*60)
        return all_data
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return all_data
    finally:
        if driver:
            driver.quit()

def extract_text_values(html_content):
    """
    Extract text values from SVG text elements in the rendered HTML.
    
    Args:
        html_content (str): The HTML content to parse
        
    Returns:
        list: List of extracted text values
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all SVG text elements with the specific attributes
    text_elements = soup.find_all('text', {
        'dy': '-0.33em',
        'font-weight': 'bold',
        'paint-order': 'stroke'
    })
    
    if not text_elements:
        print("Warning: Could not find any text elements with the specified attributes")
        # Try finding any text elements in SVG
        text_elements = soup.find_all('text')
        print(f"Found {len(text_elements)} total text elements in the HTML")
    
    # Extract the text content from each element
    values = []
    for text_elem in text_elements:
        text_content = text_elem.get_text(strip=True)
        if text_content:
            values.append(text_content)
    
    return values

if __name__ == "__main__":
    url = "https://www.svt.se/datajournalistik/bygg-en-valjare/"
    
    # TEST MODE: Set to a small number for testing, None for full scrape
    TEST_MODE = 1  # Only scrape 1 combination (9 rows)
    
    # Output to root directory
    output_dir = Path(".")
    
    if TEST_MODE:
        print(f"\n*** TEST MODE: Only scraping {TEST_MODE} combinations ***\n")
    
    # Collect data for all filter combinations (saves each row immediately)
    all_data = collect_all_combinations(url, output_dir, max_combinations=TEST_MODE)
    
    print(f"\nFinal summary:")
    print(f"  Total rows collected: {len(all_data)}")
    print(f"  CSV file: csv.csv")
    
    if all_data:
        print(f"\nFirst row sample:")
        for key, value in list(all_data[0].items())[:10]:
            print(f"  {key}: {value}")
