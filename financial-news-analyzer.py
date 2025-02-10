import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import requests
from bs4 import BeautifulSoup
import re
import yfinance as yf

# Download required NLTK data
nltk.download('vader_lexicon')
nltk.download('punkt')
nltk.download('stopwords')

class IndianStockNewsAnalyzer:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.nse_symbols = self._load_nse_symbols()
        
    def _load_nse_symbols(self):
        """Load common NSE symbols and their variations"""
        return {
            # Banking & Financial Services
            'HDFCBANK': ['HDFC Bank', 'HDFC', 'Housing Development Finance Corporation'],
            'SBIN': ['SBI', 'State Bank of India', 'State Bank'],
            'ICICIBANK': ['ICICI Bank', 'ICICI'],
            'AXISBANK': ['Axis Bank', 'Axis'],
            'KOTAKBANK': ['Kotak Bank', 'Kotak Mahindra Bank', 'Kotak'],
            'BAJFINANCE': ['Bajaj Finance', 'Bajaj Fin'],
            'BAJAJFINSV': ['Bajaj Finserv', 'Bajaj Financial Services'],
            
            # Technology
            'TCS': ['TCS', 'Tata Consultancy Services'],
            'INFY': ['Infosys', 'INFY'],
            'WIPRO': ['Wipro Limited', 'Wipro'],
            'HCLTECH': ['HCL Technologies', 'HCL Tech', 'HCL'],
            'TECHM': ['Tech Mahindra', 'Tech M'],
            'LTI': ['L&T Infotech', 'Larsen Infotech'],
            'MINDTREE': ['Mindtree Limited', 'Mindtree'],
            
            # Oil & Gas
            'RELIANCE': ['Reliance', 'RIL', 'Reliance Industries', 'Reliance Industries Limited'],
            'ONGC': ['Oil and Natural Gas Corporation', 'ONGC'],
            'IOC': ['Indian Oil Corporation', 'IndianOil', 'Indian Oil'],
            'BPCL': ['Bharat Petroleum', 'BPCL'],
            'GAIL': ['GAIL India', 'Gas Authority of India Limited'],
            
            # Automobiles
            'TATAMOTORS': ['Tata Motors', 'TAMO'],
            'MARUTI': ['Maruti Suzuki', 'Maruti', 'MSIL'],
            'M&M': ['Mahindra & Mahindra', 'Mahindra', 'M&M'],
            'BAJAJ-AUTO': ['Bajaj Auto', 'Bajaj'],
            'HEROMOTOCO': ['Hero MotoCorp', 'Hero Honda', 'Hero'],
            
            # Metals & Mining
            'TATASTEEL': ['Tata Steel', 'TISCO'],
            'HINDALCO': ['Hindalco Industries', 'Hindalco'],
            'JSWSTEEL': ['JSW Steel', 'JSW'],
            'COAL': ['Coal India', 'Coal India Limited', 'CIL'],
            
            # FMCG
            'HINDUNILVR': ['Hindustan Unilever', 'HUL', 'Hindustan Unilever Limited'],
            'ITC': ['ITC Limited', 'ITC'],
            'NESTLEIND': ['Nestle India', 'Nestle'],
            'BRITANNIA': ['Britannia Industries', 'Britannia'],
            'DABUR': ['Dabur India', 'Dabur'],
            
            # Pharma & Healthcare
            'SUNPHARMA': ['Sun Pharmaceutical', 'Sun Pharma'],
            'DRREDDY': ['Dr Reddys Laboratories', 'Dr Reddy', 'DRL'],
            'CIPLA': ['Cipla Limited', 'Cipla'],
            'DIVISLAB': ['Divi\'s Laboratories', 'Divis Lab'],
            'APOLLOHOSP': ['Apollo Hospitals', 'Apollo'],
            
            # Infrastructure & Construction
            'LT': ['Larsen & Toubro', 'L&T'],
            'ADANIENT': ['Adani Enterprises', 'Adani Ent'],
            'ADANIPORTS': ['Adani Ports', 'Adani Ports & SEZ'],
            'DLF': ['DLF Limited', 'Delhi Land & Finance'],
            
            # Cement
            'ULTRACEMCO': ['UltraTech Cement', 'Ultratech'],
            'SHREECEM': ['Shree Cement', 'Shree'],
            'ACC': ['ACC Limited', 'ACC Cement'],
            
            # Telecom
            'BHARTIARTL': ['Bharti Airtel', 'Airtel'],
            'IDEA': ['Vodafone Idea', 'VI'],
            
            # Power
            'POWERGRID': ['Power Grid Corporation', 'PowerGrid', 'Power Grid'],
            'NTPC': ['NTPC Limited', 'National Thermal Power Corporation'],
            'TATAPOWER': ['Tata Power', 'Tata Power Company'],
            
            # Consumer Durables
            'TITAN': ['Titan Company', 'Titan'],
            'HAVELLS': ['Havells India', 'Havells'],
            
            # Media & Entertainment
            'ZEEL': ['Zee Entertainment', 'Zee TV', 'ZEEL'],
            'PVR': ['PVR Limited', 'PVR Cinemas'],
            
            # Others
            'ASIANPAINT': ['Asian Paints', 'Asian Paint'],
            'PIDILITIND': ['Pidilite Industries', 'Pidilite'],
            'HDFCLIFE': ['HDFC Life Insurance', 'HDFC Life'],
            'SBILIFE': ['SBI Life Insurance', 'SBI Life'],
            'ADANIGREEN': ['Adani Green Energy', 'Adani Green'],
            'NAUKRI': ['Info Edge', 'Naukri', 'Info Edge India']
            # Add more symbols as needed
        }
    
    def _extract_stock_mentions(self, text):
        """Extract mentioned stock symbols from text"""
        mentioned_stocks = set()
        
        for symbol, variations in self.nse_symbols.items():
            for variation in variations:
                if variation.lower() in text.lower():
                    mentioned_stocks.add(symbol)
                    
        return list(mentioned_stocks)
    
    def analyze_news(self, news_text):
        """Analyze news text and return sentiment for mentioned stocks"""
        results = []
        
        # Get sentiment scores
        sentiment = self.sia.polarity_scores(news_text)
        
        # Extract mentioned stocks
        stocks = self._extract_stock_mentions(news_text)
        
        for stock in stocks:
            # Determine recommendation based on compound sentiment
            if sentiment['compound'] >= 0.2:
                recommendation = 'BUY'
            elif sentiment['compound'] <= -0.2:
                recommendation = 'SELL'
            else:
                recommendation = 'HOLD'
            
            result = {
                'stock': stock,
                'sentiment_score': sentiment['compound'],
                'positive': sentiment['pos'],
                'negative': sentiment['neg'],
                'neutral': sentiment['neu'],
                'recommendation': recommendation
            }
            results.append(result)
            
        return results
    
    def get_stock_price(self, symbol):
        """Get current stock price from Yahoo Finance"""
        try:
            stock = yf.Ticker(f"{symbol}.NS")
            return stock.info.get('currentPrice', None)
        except:
            return None
    
    def analyze_news_with_price(self, news_text):
        """Analyze news and include current stock prices"""
        analysis = self.analyze_news(news_text)
        
        for result in analysis:
            price = self.get_stock_price(result['stock'])
            result['current_price'] = price
            
        return analysis

def format_analysis_report(analysis_results):
    """Format analysis results into a readable report"""
    report = []
    for result in analysis_results:
        current_price =  result['current_price'] if result['current_price'] else 'N/A'
        stock_report = f"""
Stock: {result['stock']}
Sentiment Score: {result['sentiment_score']:.2f}
Current Price: ₹{current_price:.2f}
Recommendation: {result['sentiment_score']}
Details:
- Positive: {result['positive']:.2f}
- Negative: {result['negative']:.2f}
- Neutral: {result['neutral']:.2f}
"""
        report.append(stock_report)
    
    return "\n".join(report)

def getAnalysis(news):
    analyzer = IndianStockNewsAnalyzer()
    # Analyze news
    results = analyzer.analyze_news_with_price(news)
    return format_analysis_report(results)
# Example usage
if __name__ == "__main__":
    analyzer = IndianStockNewsAnalyzer()
    
    # Example news text
    news = """
    The markets continue to remain under pressure since the inception of the October series. An options-based trend level broke, which suggested that the month could remain in a corrective/consolidative phase.A reversal attempt was made with asupport levelof 24,700 but the market failed to sustain above the same as well.“As of now we believe the market is failing to cross and sustain above its previoustrading sessionshigh as well and unless the same happens downside pressure could persist,” said Sahaj Agrawal, Senior Vice President: Head of Derivatives Research at,Kotak Securities.Agrawal further stated that he expects volatility to remain high for the near term and expects selling pressure to continue until any strong reversal pattern matures.From the medium term perspective, the support zone is seen around the 23,500-23,700 mark from where momentum is expected to reverse.Stock TradingOptions Trading Course For BeginnersBy - Chetan Panchamia, Options TraderView ProgramStock TradingPoint & Figure Chart Mastery: A Comprehensive Trading GuideBy - Mukta Dhamankar, Full Time Trader, 15 Years Experience, InstructorView ProgramStock TradingTechnical Trading Made Easy: Online Certification CourseBy - Souradeep Dey, Equity and Commodity Trader, TrainerView ProgramStock TradingTechnical Analysis Demystified: A Complete Guide to TradingBy - Kunal Patel, Options Trader, InstructorView ProgramStock TradingIchimoku Trading Unlocked: Expert Analysis and StrategyBy - Dinesh Nagpal, Full Time Trader, Ichimoku & Trading Psychology ExpertView ProgramStock TradingAlgo Trading Made EasyBy - Vivek Gadodia, Partner at Dravyaniti Consulting and RBT Algo SystemsView ProgramStock TradingMarkets 102: Mastering Sentiment Indicators for Swing and Positional TradingBy - Rohit Srivastava, Founder- Indiacharts.comView ProgramStock TradingDerivative Analytics Made EasyBy - Vivek Bajaj, Co Founder- Stockedge and ElearnmarketsView ProgramStock TradingCandlesticks Made Easy: Candlestick Pattern CourseBy - elearnmarkets, Financial Education by StockEdgeView ProgramStock TradingMacroeconomics Made Easy: Online Certification CourseBy - Anirudh Saraf, Founder- Saraf A & Associates, Chartered AccountantView ProgramStock TradingTechnical Analysis Made Easy: Online Certification CourseBy - Souradeep Dey, Equity and Commodity Trader, TrainerView ProgramStock TradingMastering Options Selling: Advanced Strategies for SuccessBy - CA Manish Singh, Chartered Accountant, Professional Equity and Derivative TraderView ProgramFrom an OI perspective, highest call concentration is placed at 25,000 and 25,500 strikes while maximum Put is concentrated at 24,000 and 24,500.With this, Sahaj Agrawal suggests deploying aBear Put SpreadinNiftyto make potentialgainsfrom the expected consolidation.Bear Put SpreadTraders use this strategy when they expect the price of an underlying to decline in the near future. This involves buying and selling put options of the same expiry but different strike prices.A higher strike price put is bought and a lower priced one is sold. The higher priced put is in-the-money (ITM) while a lower priced one is an out-of-the-money option. This strategy results in a net debit for the trader as the cost of the ITM put gets adjusted with the cash flow from shorting the OTM put.ETMarkets.com(Prices considered as of October 24)Below is the payoff graph of the strategy
    """
    
    # Analyze news
    results = analyzer.analyze_news_with_price(news)
    
    # Print formatted report
    print(format_analysis_report(results))
