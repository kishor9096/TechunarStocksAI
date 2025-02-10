import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API keys (you'll need to sign up for these services)
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

def fetch_news(sources, stocks):
    """
    Fetch news from various sources based on user configuration.
    
    :param sources: List of news sources selected by the user
    :param stocks: List of stocks selected by the user
    :return: List of news articles
    """
    news_articles = []

    for source in sources:
        if source == 'Economic Times':
            news_articles.extend(fetch_economic_times(stocks))
        elif source == 'Moneycontrol':
            news_articles.extend(fetch_moneycontrol(stocks))
        elif source == 'LiveMint':
            news_articles.extend(fetch_livemint(stocks))
        elif source in ['Business Standard', 'Financial Express', 'NDTV Profit']:
            news_articles.extend(fetch_newsapi(source, stocks))
        elif source == 'Bloomberg Quint':
            news_articles.extend(fetch_bloomberg_quint(stocks))

    return news_articles

def fetch_economic_times(stocks):
    # Web scraping implementation for Economic Times
    # This is a placeholder and needs to be implemented
    return []

def fetch_moneycontrol(stocks):
    # Web scraping implementation for Moneycontrol
    # This is a placeholder and needs to be implemented
    return []

def fetch_livemint(stocks):
    # Web scraping implementation for LiveMint
    # This is a placeholder and needs to be implemented
    return []

def fetch_newsapi(source, stocks):
    # Using NewsAPI to fetch news
    base_url = "https://newsapi.org/v2/everything"
    
    articles = []
    for stock in stocks:
        params = {
            'apiKey': NEWSAPI_KEY,
            'q': stock,
            'sources': source.lower().replace(' ', '-'),
            'language': 'en',
            'sortBy': 'publishedAt'
        }
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            articles.extend(data['articles'])
    
    return articles

def fetch_bloomberg_quint(stocks):
    # Using Finnhub API to fetch Bloomberg news
    base_url = "https://finnhub.io/api/v1/news"
    
    articles = []
    for stock in stocks:
        params = {
            'token': FINNHUB_API_KEY,
            'category': 'general',
            'symbol': stock
        }
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            articles.extend(data)
    
    return articles

# Example usage
if __name__ == '__main__':
    test_sources = ['Economic Times', 'Moneycontrol', 'Business Standard']
    test_stocks = ['RELIANCE', 'TCS', 'HDFC']
    news = fetch_news(test_sources, test_stocks)
    print(f"Fetched {len(news)} news articles")
