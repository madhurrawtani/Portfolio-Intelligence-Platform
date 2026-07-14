import json
import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define Pydantic models for structured output
class StockPosition(BaseModel):
    ticker_or_name: str = Field(description="The ticker symbol or name of the stock/asset as displayed")
    quantity: float = Field(description="The number of shares or units held")
    average_price: float = Field(description="The average purchase price per share/unit")
    current_price: Optional[float] = Field(None, description="The current market price per share/unit as displayed, if available")
    current_value: Optional[float] = Field(None, description="The current total market value of the position as displayed, if available")
    todays_pnl: Optional[float] = Field(None, description="Today's Profit & Loss value for this position as displayed, if available")

class PortfolioData(BaseModel):
    positions: List[StockPosition]
    overall_portfolio_value: Optional[float] = Field(None, description="The overall total value of the portfolio as displayed in the screenshot, if available")

# Canonical stock mapping dictionary for normalization
CANONICAL_MAPPINGS = {
    # Indian Stocks Examples
    "hdfcbank": "HDFCBANK",
    "hdfc bank": "HDFCBANK",
    "hdfc bank ltd": "HDFCBANK",
    "hdfc bank limited": "HDFCBANK",
    "hdfc": "HDFCBANK",
    
    "reliance": "RELIANCE",
    "reliance industries": "RELIANCE",
    "reliance industries ltd": "RELIANCE",
    "reliance industries limited": "RELIANCE",
    
    "tcs": "TCS",
    "tata consultancy services": "TCS",
    "tata consultancy services ltd": "TCS",
    "tata consultancy services limited": "TCS",
    
    "infosys": "INFY",
    "infosys ltd": "INFY",
    "infosys limited": "INFY",
    "infy": "INFY",

    "icici": "ICICIBANK",
    "icicibank": "ICICIBANK",
    "icici bank": "ICICIBANK",
    "icici bank ltd": "ICICIBANK",
    "icici bank limited": "ICICIBANK",

    # US Stocks Examples
    "apple": "AAPL",
    "apple inc": "AAPL",
    "apple inc.": "AAPL",
    "aapl": "AAPL",

    "microsoft": "MSFT",
    "microsoft corp": "MSFT",
    "microsoft corp.": "MSFT",
    "microsoft corporation": "MSFT",
    "msft": "MSFT",

    "tesla": "TSLA",
    "tesla inc": "TSLA",
    "tesla inc.": "TSLA",
    "tsla": "TSLA",

    "google": "GOOGL",
    "alphabet": "GOOGL",
    "alphabet inc": "GOOGL",
    "alphabet inc.": "GOOGL",
    "googl": "GOOGL",
    "goog": "GOOGL",
}

def clean_stock_name(name: str) -> str:
    """
    Cleans a stock name by removing punctuation, extra spaces, and common suffixes
    (e.g., Ltd, Limited, Inc, Corp, Corporation) to help normalize matches.
    """
    if not name:
        return ""
    
    # Lowercase and strip whitespace
    cleaned = name.strip().lower()
    
    # Remove punctuation except spaces
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    
    # Remove common corporate suffixes
    suffixes = [
        r'\bltd\b', r'\blimited\b', r'\binc\b', r'\bcorp\b', 
        r'\bcorporation\b', r'\bco\b', r'\bcompany\b', r'\bplc\b'
    ]
    for suffix in suffixes:
        cleaned = re.sub(suffix, '', cleaned)
        
    # Replace multiple spaces with a single space and strip again
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def normalize_stock_name(name: str) -> str:
    """
    Normalizes a stock name using rule-based clean-up and a canonical dictionary mapping.
    """
    if not name:
        return "UNKNOWN"
    
    cleaned = clean_stock_name(name)
    
    # Check if we have a direct canonical mapping
    if cleaned in CANONICAL_MAPPINGS:
        return CANONICAL_MAPPINGS[cleaned]
    
    # Fallback: return cleaned name in uppercase (with suffixes removed)
    return cleaned.upper() if cleaned else name.strip().upper()

def extract_portfolio_from_image(image_path: str, api_key: Optional[str] = None) -> PortfolioData:
    """
    Uses Gemini Vision API to extract stock data from a portfolio screenshot image.
    Supports either an environment variable GEMINI_API_KEY or an explicitly passed api_key.
    """
    # Prefer explicitly passed API key, fallback to environment
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API key not found. Please set GEMINI_API_KEY env variable or pass it in.")
    
    try:
        from google import genai
        from google.genai import types
        
        # Initialize Google GenAI Client
        client = genai.Client(api_key=key)
        
        # Open image using Pillow
        image = Image.open(image_path)
        
        prompt = (
            "You are an expert financial document extractor. "
            "Analyze the attached portfolio screenshot and extract all listed stock/asset positions. "
            "For each stock/asset, extract the stock name/ticker, holding quantity, and average buy price. "
            "Additionally, if available, extract the current stock price, current position value, and today's P&L. "
            "Also, if available, extract the overall portfolio value displayed in the screenshot. "
            "Return the list and data formatted exactly according to the requested JSON schema."
        )
        
        # Use gemini-2.5-flash which is standard and has visual capabilities
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PortfolioData,
            ),
        )
        
        # Parse the JSON response
        data = json.loads(response.text)
        return PortfolioData(**data)
        
    except ImportError:
        # Fallback to google-generativeai SDK if google-genai is not installed/working
        import google.generativeai as genai
        
        genai.configure(api_key=key)
        image = Image.open(image_path)
        
        prompt = (
            "Analyze this portfolio screenshot. Extract stock position details: "
            "stock name/ticker, holding quantity, and average buy price. "
            "Additionally, if available in the screenshot, extract the current stock price, current position value, and today's P&L for each stock. "
            "Also extract the overall portfolio value if visible. "
            "Return JSON in the format:\n"
            "{\n"
            "  \"positions\": [\n"
            "    {\n"
            "      \"ticker_or_name\": \"string\",\n"
            "      \"quantity\": float,\n"
            "      \"average_price\": float,\n"
            "      \"current_price\": float or null,\n"
            "      \"current_value\": float or null,\n"
            "      \"todays_pnl\": float or null\n"
            "    }\n"
            "  ],\n"
            "  \"overall_portfolio_value\": float or null\n"
            "}"
        )
        
        # gemini-1.5-flash or gemini-2.5-flash
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([image, prompt], generation_config={"response_mime_type": "application/json"})
        
        data = json.loads(response.text)
        return PortfolioData(**data)
