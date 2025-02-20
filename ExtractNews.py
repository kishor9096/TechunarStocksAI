import os
import configparser
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime
import mysql.connector
from urllib.parse import urlparse
import json
import threading
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def extract_and_save_news():
    # Read URLs and Ollama config from app.config
    config = configparser.ConfigParser()
    config.read('app.config')
    urls = config.get('MoneyControl', 'cms_urls').split(',')
    ollama_api_url = config.get('Ollama', 'api_url')
    ollama_model = config.get('Ollama', 'model')

    # Connect to the database using environment variables
    # Connect to the database using environment variables
    conn = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        port=os.getenv('MYSQL_PORT'),
        database=os.getenv('MAX_PAIN_DATABASE'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD')
    )
    cursor = conn.cursor()

    # Select the database
    #cursor.execute(f"USE {os.getenv('MAX_PAIN_DATABASE')}")

    # Create table if not exists (updated schema)
    cursor.execute('''CREATE TABLE IF NOT EXISTS news_articles
                      (title TEXT, description TEXT, link TEXT, pubDate TIMESTAMP, article TEXT,
                       sentiment TEXT, recommendation TEXT, stocks JSON, PRIMARY KEY (link(255)))''')
    
    for url in urls:
        # Fetch and parse XML content
        response = requests.get(url.strip())
        root = ET.fromstring(response.content) if response.status_code == 200 else None

        for item in root.findall('.//item') if root is not None else []:
            title = item.find('title').text
            description = item.find('description').text
            link = item.find('link').text
            pubDate_str = item.find('pubDate').text
            # Convert pubDate string to datetime object
            pubDate = convert_to_datetime(pubDate_str)

            # Check if the article already exists in the database
            cursor.execute("SELECT * FROM news_articles WHERE link = %s", (link,))
            if cursor.fetchone() is None:
                # Extract full article text based on domain
                article_text = extract_article_text(link)

                # Perform sentiment analysis, get recommendation, and extract stocks using Ollama
                sentiment, recommendation, stocks = analyze_content(article_text, ollama_api_url, ollama_model)

                # Insert into database (updated query)
                cursor.execute('''INSERT INTO news_articles 
                                  (title, description, link, pubDate, article, sentiment, recommendation, stocks)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                               (title, description, link, pubDate.isoformat(), article_text, sentiment, recommendation, json.dumps(stocks)))
                conn.commit()
                print(f"Added new article: {title} - Stocks: {stocks} - Sentiment: {sentiment}, Recommendation: {recommendation}")
            else:
                print(f"Article already exists: {title}")

    conn.close()

def convert_to_datetime(date_string):
    return datetime.strptime(date_string, "%a, %d %b %Y %H:%M:%S %z")

def extract_article_text(url):
    article_response = requests.get(url)
    article_soup = BeautifulSoup(article_response.text, 'html.parser')
    domain = urlparse(url).netloc
    
    if 'moneycontrol.com' in domain:
        content_div = article_soup.find('div', class_='content_wrapper')
        return content_div.get_text(strip=True) if content_div else ""
    elif 'economictimes.indiatimes.com' in domain:
        data_elements = article_soup.find_all('main', class_='clr customclr')
        elementText = ""
        if data_elements:
            for element in data_elements:
                for tag in ['img', 'a']:
                    for sub_tag in element.find_all(tag):
                        sub_tag.decompose()
            for element in data_elements:
                elementText += element.get_text(strip=True)
            
        return elementText
    else:
        # Default case or for unknown domains
        return article_soup.get_text(strip=True)

def analyze_content(text, api_url, model):
    prompt = f"""Consider yourself as a stock market analyst. Analyze the following news article and using your expertise of stock market provide the following information:
1. Sentiment (POSITIVE, NEGATIVE, or NEUTRAL)
2. Stock recommendation (BUY, SELL, or HOLD)
3. stock in discussion discussion, in case of multiple stocks provide comma separated 

{text}

Respond in the following JSON format:
{{
    "sentiment": "POSITIVE/NEGATIVE/NEUTRAL",
    "recommendation": "BUY/SELL/HOLD",
    "stocks": [
        {{"name": "Stock Name 1", "code": "STOCK_CODE_1"}},
        {{"name": "Stock Name 2", "code": "STOCK_CODE_2"}},
        ...
    ]
}}
"""

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(api_url, json=payload)
    if response.status_code == 200:
        result = response.json()
        try:
            output = json.loads(result['response'])
            return output['sentiment'], output['recommendation'], output['stocks']
        except json.JSONDecodeError:
            print(f"Error parsing Ollama API response: {result['response']}")
            return "UNKNOWN", "UNKNOWN", []
    else:
        print(f"Error calling Ollama API: {response.status_code}")
        return "UNKNOWN", "UNKNOWN", []

# Replace the direct function call with the background thread
if __name__ == "__main__":
    extract_and_save_news()
