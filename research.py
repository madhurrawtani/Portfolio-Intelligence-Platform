import os
import json
import re
import requests
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

# Pydantic schema for structured research report output (Phase 3 + Enhanced Intelligence + Sector)
class ResearchReport(BaseModel):
    stock: str = Field(description="The ticker symbol or name of the stock")
    research_available: str = Field(description="Yes if research/coverage is found, No otherwise")
    recommendation: str = Field("Research Not Available", description="Recommendation rating (e.g. Buy, Accumulate, Hold, Reduce, Sell)")
    confidence_score: Optional[float] = Field(None, description="Calculated confidence percentage (e.g. 85.0) based on factors")
    target_price: Optional[float] = Field(None, description="The target price per share, if available")
    key_reasons: List[str] = Field(default_factory=list, description="Top 3-4 key reasons/drivers backing the recommendation")
    research_source: str = Field(description="Clear citation of sources used (e.g. Nirmal Bang, Motilal Oswal, Nirmal Bang + Motilal Oswal, or Web Research)")
    research_date: Optional[str] = Field(None, description="Actual publication date in YYYY-MM-DD format if available in context, else null. DO NOT invent dates.")
    key_takeaway: Optional[str] = Field(None, description="A 1-2 sentence key takeaway summary or outlook")
    recommendation_type: str = Field(description="Classification of recommendation source: Must be either 'Nirmal Bang', 'Motilal Oswal', 'Nirmal Bang + Motilal Oswal', or 'Web Research'")
    ai_provider_used: Optional[str] = Field(None, description="The AI Provider and model used to generate this analysis")
    sector: Optional[str] = Field(None, description="The sector or industry of the stock (e.g. Banking, Technology, Energy, Automobile, Retail, FMCG)")
    
    # Enhanced intelligence fields
    raw_score: Optional[int] = Field(None, description="Calculated raw score out of max_score")
    max_score: Optional[int] = Field(None, description="Maximum possible score based on factors")
    factors_breakdown: Dict[str, str] = Field(default_factory=dict, description="Factor-by-factor categorical evaluations")

# Python helper to calculate rule-based confidence from categorical factor evaluations
def calculate_confidence_score_from_factors(factors: Dict[str, str]) -> tuple:
    score = 0
    max_score = 10
    
    # 1. Analyst Sentiment: Positive (+2), Neutral (+1), Negative (0)
    sentiment = factors.get("analyst_sentiment", "neutral").lower()
    if "positive" in sentiment:
        score += 2
    elif "neutral" in sentiment:
        score += 1
        
    # 2. Target Upside: Positive (+2), Neutral (+1), Negative (0)
    upside = factors.get("target_upside", "neutral").lower()
    if "positive" in upside:
        score += 2
    elif "neutral" in upside:
        score += 1
        
    # 3. Revenue Growth: Positive (+1), Neutral (0), Negative (-1)
    rev = factors.get("revenue_growth", "neutral").lower()
    if "positive" in rev:
        score += 1
    elif "negative" in rev:
        score -= 1
        
    # 4. Profitability Outlook: Positive (+1), Neutral (0), Negative (-1)
    prof = factors.get("profitability_outlook", "neutral").lower()
    if "positive" in prof:
        score += 1
    elif "negative" in prof:
        score -= 1
        
    # 5. Balance Sheet Strength: Positive (+1), Neutral (0), Negative (-1)
    bs = factors.get("balance_sheet_strength", "neutral").lower()
    if "positive" in bs:
        score += 1
    elif "negative" in bs:
        score -= 1
        
    # 6. Sector Outlook: Positive (+1), Neutral (0), Negative (-1)
    sec = factors.get("sector_outlook", "neutral").lower()
    if "positive" in sec:
        score += 1
    elif "negative" in sec:
        score -= 1
        
    # 7. Risk Factors: Low (+1), Moderate (0), High (-1)
    risks = factors.get("risk_factors", "moderate").lower()
    if "low" in risks:
        score += 1
    elif "high" in risks:
        score -= 1
        
    # 8. Valuation Concerns: Low (+1), Moderate (0), High (-1)
    val = factors.get("valuation_concerns", "moderate").lower()
    if "low" in val:
        score += 1
    elif "high" in val:
        score -= 1
        
    # Clamp score to a minimum of 0
    score = max(0, score)
    confidence_pct = (score / max_score) * 100
    return score, max_score, confidence_pct

# Helper function to perform DuckDuckGo search without API Keys
def search_duckduckgo(query: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Use JS-free HTML search interface
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        
        # Regex to extract snippets from result container
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', response.text, re.DOTALL)
        
        cleaned_snippets = []
        for snippet in snippets[:4]:  # Top 4 results
            txt = re.sub(r'<[^>]+>', '', snippet)
            txt = (txt.replace("&quot;", '"')
                      .replace("&amp;", "&")
                      .replace("&lt;", "<")
                      .replace("&gt;", ">")
                      .replace("&#x27;", "'")
                      .replace("&#39;", "'"))
            cleaned_snippets.append(txt.strip())
            
        if cleaned_snippets:
            return "\n".join(cleaned_snippets)
        return ""
    except Exception as e:
        return f"Search failed: {str(e)}"

# Helper to gather search context for a stock from independent sources
def retrieve_stock_research_context(stock_name: str) -> str:
    # 1. Primary Source Query: Nirmal Bang
    nb_query = f"Nirmal Bang equity research report {stock_name} target price"
    nb_results = search_duckduckgo(nb_query)
    
    # 2. Secondary Source Query: Motilal Oswal
    mo_query = f"Motilal Oswal equity research report {stock_name} target price"
    mo_results = search_duckduckgo(mo_query)
    
    # 3. Fallback Query: Web Research
    general_query = f"{stock_name} stock analyst recommendations target price outlook news"
    general_results = search_duckduckgo(general_query)
    
    context = ""
    if nb_results:
        context += f"--- Search Results for Nirmal Bang report on {stock_name} ---\n{nb_results}\n\n"
    if mo_results:
        context += f"--- Search Results for Motilal Oswal report on {stock_name} ---\n{mo_results}\n\n"
    if general_results:
        context += f"--- Search Results for General Web Research on {stock_name} ---\n{general_results}\n\n"
        
    return context.strip() if context else "No research results retrieved from web search."

# Base Research Provider Interface
class BaseLlmProvider:
    def __init__(self, name: str, model_name: str, api_key: str):
        self.name = name
        self.model_name = model_name
        self.api_key = api_key

    def generate_batch_research(self, stocks_data: List[dict]) -> List[dict]:
        raise NotImplementedError

    def _parse_json_array(self, text: str) -> List[dict]:
        text = text.strip()
        match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        try:
            return json.loads(text)
        except Exception as e:
            raise ValueError(f"Failed to parse text as JSON array: {str(e)}. Raw text snippet: {text[:500]}")

# Gemini LLM Provider
class GeminiLlmProvider(BaseLlmProvider):
    def generate_batch_research(self, stocks_data: List[dict]) -> List[dict]:
        stocks_info = ""
        for item in stocks_data:
            stocks_info += f"Stock Ticker: {item['stock']}\n"
            if item['context'] and "Search failed" not in item['context'] and "No research results" not in item['context']:
                stocks_info += f"Search Findings Context:\n{item['context']}\n"
            else:
                stocks_info += "Please use your google_search tool to find the latest research reports, consensus ratings, target prices, and dates for this stock (checking Nirmal Bang and Motilal Oswal first, then generic web search).\n"
            stocks_info += "----------------------------------------\n"
            
        prompt = (
            "You are an expert equity analyst. You are provided with stocks and their findings (or you should search for them using google_search).\n"
            "Analyze these findings and compile a structured research report for each stock. "
            "For each stock, inspect the context and evaluate:\n"
            "1. Sources Check: Determine if there is active coverage in the context from: 1) Nirmal Bang, 2) Motilal Oswal. "
            "If both have active coverage, synthesize a consensus recommendation and set 'recommendation_type' and 'research_source' to 'Nirmal Bang + Motilal Oswal'. "
            "If only one is present, use that broker's rating and details (e.g. 'Nirmal Bang' or 'Motilal Oswal'). "
            "If neither broker has active reports, fallback to general web consensus and set 'recommendation_type' and 'research_source' to 'Web Research'.\n"
            "2. Date Extraction: Extract the actual publication date in YYYY-MM-DD format if explicitly mentioned in the context. "
            "If no specific publication date is found, set 'research_date' to null. DO NOT guess or make up any dates.\n"
            "3. Sector Identification: Identify the sector or industry of the stock (e.g. Banking, IT Services, Technology, Energy, Automobile, Retail, FMCG) based on the search context or general profile. Set under 'sector'.\n"
            "4. Evidence Factors: Categorize the following 8 indicators for 'factors_breakdown' strictly as one of the specified string values:\n"
            "   - analyst_sentiment: positive, neutral, or negative\n"
            "   - target_upside: positive, neutral, or negative\n"
            "   - revenue_growth: positive, neutral, or negative\n"
            "   - profitability_outlook: positive, neutral, or negative\n"
            "   - balance_sheet_strength: positive, neutral, or negative\n"
            "   - sector_outlook: positive, neutral, or negative\n"
            "   - risk_factors: low, moderate, or high\n"
            "   - valuation_concerns: low, moderate, or high\n\n"
            "Stocks to analyze:\n"
            f"{stocks_info}\n"
            "Response Instructions:\n"
            "You must return the analysis ONLY as a valid JSON array matching the following schema. "
            "Do not include any formatting, preambles, explanation, or markdown wrappers. "
            "Each object in the array must have the following fields:\n"
            "- stock: string\n"
            "- research_available: string ('Yes' or 'No')\n"
            "- recommendation: string (e.g. 'Buy', 'Accumulate', 'Hold', 'Reduce', 'Sell', or 'Research Not Available')\n"
            "- target_price: float or null (the target price in ₹)\n"
            "- key_reasons: list of strings (3-4 bullet points)\n"
            "- research_source: string (citation of sources used)\n"
            "- research_date: string or null (YYYY-MM-DD or null)\n"
            "- key_takeaway: string or null (1-2 sentence summary)\n"
            "- recommendation_type: string ('Nirmal Bang', 'Motilal Oswal', 'Nirmal Bang + Motilal Oswal', or 'Web Research')\n"
            "- sector: string (classified sector or industry)\n"
            "- factors_breakdown: object containing the 8 factors evaluated above\n"
        )
        
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_name or 'gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    tools=[{"google_search": {}}]
                )
            )
            content = response.text.strip()
        except Exception:
            # Fallback to google-generativeai SDK
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name or 'gemini-2.5-flash', tools=['google_search'])
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            content = response.text.strip()
            
        return self._parse_json_array(content)

# OpenRouter LLM Provider
class OpenRouterLlmProvider(BaseLlmProvider):
    def generate_batch_research(self, stocks_data: List[dict]) -> List[dict]:
        stocks_info = ""
        for item in stocks_data:
            stocks_info += f"Stock Ticker: {item['stock']}\n"
            if item['context'] and "Search failed" not in item['context'] and "No research results" not in item['context']:
                stocks_info += f"Search Findings Context:\n{item['context']}\n"
            else:
                stocks_info += "Please research this stock using your search tools (checking Nirmal Bang and Motilal Oswal first, then web search).\n"
            stocks_info += "----------------------------------------\n"
            
        prompt = (
            "You are an expert equity analyst. You are provided with stocks and their findings.\n"
            "Analyze these findings and compile a structured research report for each stock. "
            "For each stock, inspect the context and evaluate:\n"
            "1. Sources Check: Determine if there is active coverage in the context from: 1) Nirmal Bang, 2) Motilal Oswal. "
            "If both have active coverage, synthesize a consensus recommendation and set 'recommendation_type' and 'research_source' to 'Nirmal Bang + Motilal Oswal'. "
            "If only one is present, use that broker's rating and details (e.g. 'Nirmal Bang' or 'Motilal Oswal'). "
            "If neither broker has active reports, fallback to general web consensus and set 'recommendation_type' and 'research_source' to 'Web Research'.\n"
            "2. Date Extraction: Extract the actual publication date in YYYY-MM-DD format if explicitly mentioned in the context. "
            "If no specific publication date is found, set 'research_date' to null. DO NOT guess or make up any dates.\n"
            "3. Sector Identification: Identify the sector or industry of the stock (e.g. Banking, IT Services, Technology, Energy, Automobile, Retail, FMCG) based on the search context or general profile. Set under 'sector'.\n"
            "4. Evidence Factors: Categorize the following 8 indicators for 'factors_breakdown' strictly as one of the specified string values:\n"
            "   - analyst_sentiment: positive, neutral, or negative\n"
            "   - target_upside: positive, neutral, or negative\n"
            "   - revenue_growth: positive, neutral, or negative\n"
            "   - profitability_outlook: positive, neutral, or negative\n"
            "   - balance_sheet_strength: positive, neutral, or negative\n"
            "   - sector_outlook: positive, neutral, or negative\n"
            "   - risk_factors: low, moderate, or high\n"
            "   - valuation_concerns: low, moderate, or high\n\n"
            "Stocks to analyze:\n"
            f"{stocks_info}\n"
            "Response Instructions:\n"
            "You must return the analysis ONLY as a valid JSON array matching the following schema. "
            "Do not include any formatting, preambles, explanation, or markdown wrappers. "
            "Each object in the array must have the following fields:\n"
            "- stock: string\n"
            "- research_available: string ('Yes' or 'No')\n"
            "- recommendation: string (e.g. 'Buy', 'Accumulate', 'Hold', 'Reduce', 'Sell', or 'Research Not Available')\n"
            "- target_price: float or null (the target price in ₹)\n"
            "- key_reasons: list of strings (3-4 bullet points)\n"
            "- research_source: string (citation of sources used)\n"
            "- research_date: string or null (YYYY-MM-DD or null)\n"
            "- key_takeaway: string or null (1-2 sentence summary)\n"
            "- recommendation_type: string ('Nirmal Bang', 'Motilal Oswal', 'Nirmal Bang + Motilal Oswal', or 'Web Research')\n"
            "- sector: string (classified sector or industry)\n"
            "- factors_breakdown: object containing the 8 factors evaluated above\n"
        )
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/google/antigravity",
            "X-Title": "AI Portfolio Analyzer"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=35
        )
        response.raise_for_status()
        resp_data = response.json()
        
        if 'choices' not in resp_data or not resp_data['choices']:
            raise ValueError(f"OpenRouter returned empty response: {json.dumps(resp_data)}")
            
        content = resp_data['choices'][0]['message']['content'].strip()
        return self._parse_json_array(content)

# Lightweight Research Cache Layer
class ResearchCache:
    def __init__(self, cache_file: str = "outputs/research_cache.json"):
        self.cache_file = cache_file
        self.cache = {}
        self.load()

    def load(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}
        else:
            self.cache = {}

    def save(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=4)
        except Exception:
            pass

    def get(self, stock: str) -> Optional[dict]:
        if stock not in self.cache:
            return None
        
        entry = self.cache[stock]
        timestamp_str = entry.get("timestamp")
        if not timestamp_str:
            return None
            
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - timestamp
            if age.total_seconds() < 24 * 3600:
                return entry.get("report")
        except Exception:
            pass
            
        return None

    def set(self, stock: str, report: dict):
        self.cache[stock] = {
            "timestamp": datetime.now().isoformat(),
            "report": report
        }
        self.save()

# Research Manager Orchestrating Priority & Caching Flow
class ResearchManager:
    def __init__(self, api_key: Optional[str] = None, openrouter_key: Optional[str] = None):
        self.gemini_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY", "")
        self.provider_type = os.getenv("RESEARCH_PROVIDER", "openrouter").lower()
        self.model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
        self.cache = ResearchCache()

    def get_portfolio_research(self, stocks: List[str], force_refresh: bool = False) -> List[ResearchReport]:
        results = []
        stocks_to_fetch = []
        
        # 1. Cache Check
        for stock in stocks:
            cached_report_dict = None
            if not force_refresh:
                cached_report_dict = self.cache.get(stock)
                
            if cached_report_dict:
                report = ResearchReport(**cached_report_dict)
                # Indicate result came from cache
                orig_type = report.recommendation_type
                if "Cache" not in orig_type:
                    report.recommendation_type = f"Cache ({orig_type})"
                results.append(report)
            else:
                stocks_to_fetch.append(stock)
                
        if not stocks_to_fetch:
            # Reorder cache-hits to match original order
            sorted_results = []
            for stock in stocks:
                for r in results:
                    if r.stock == stock:
                        sorted_results.append(r)
                        break
            return sorted_results
            
        # 2. Retrieval phase: Search web context for non-cached stocks
        stocks_data = []
        for stock in stocks_to_fetch:
            context = retrieve_stock_research_context(stock)
            stocks_data.append({
                "stock": stock,
                "context": context
            })
            
        # 3. Batch LLM generation phase
        try:
            if self.provider_type == "gemini":
                if not self.gemini_key:
                    raise ValueError("Gemini API Key is missing for Gemini Research Provider.")
                llm = GeminiLlmProvider(
                    name="Gemini",
                    model_name="gemini-2.5-flash",
                    api_key=self.gemini_key
                )
            else:
                if not self.openrouter_key or "your_actual" in self.openrouter_key:
                    raise ValueError("OpenRouter API Key is missing or invalid. Please configure it in .env or sidebar.")
                llm = OpenRouterLlmProvider(
                    name="OpenRouter",
                    model_name=self.model_name,
                    api_key=self.openrouter_key
                )
                
            new_reports_data = llm.generate_batch_research(stocks_data)
            
            # Post-process, calculate scores, handle date substitutes, and build report objects
            for r in new_reports_data:
                # 1. Python scoring
                factors = r.get("factors_breakdown", {})
                raw_score, max_score, confidence_pct = calculate_confidence_score_from_factors(factors)
                r["raw_score"] = raw_score
                r["max_score"] = max_score
                r["confidence_score"] = confidence_pct
                
                # 2. Date Handler: DO NOT invent dates. Substitute missing with retrieval date
                pub_date = r.get("research_date")
                if not pub_date or str(pub_date).strip().lower() in ["null", "none", ""]:
                    r["research_date"] = f"Research Retrieved On: {datetime.now().strftime('%Y-%m-%d')}"
                
                # 3. Provider Tag
                r["ai_provider_used"] = f"{self.provider_type.upper()} ({self.model_name})"
                
                report_obj = ResearchReport(**r)
                
                # 4. Save to cache
                self.cache.set(report_obj.stock, report_obj.model_dump())
                results.append(report_obj)
                
        except Exception as e:
            # Fallback error items per failed stock
            for stock in stocks_to_fetch:
                err_report = ResearchReport(
                    stock=stock,
                    research_available="No",
                    recommendation="Research Not Available",
                    confidence_score=None,
                    target_price=None,
                    key_reasons=[f"Research generation failed: {str(e)}"],
                    research_source="System Error",
                    research_date=f"Research Retrieved On: {datetime.now().strftime('%Y-%m-%d')}",
                    key_takeaway=f"Failed to generate research for {stock}.",
                    recommendation_type="Web Research",
                    ai_provider_used=f"{self.provider_type.upper()} (Error)",
                    sector=None,
                    raw_score=None,
                    max_score=None,
                    factors_breakdown={}
                )
                results.append(err_report)
                
        # 4. Sort results back to matching the requested stocks list order
        sorted_results = []
        for stock in stocks:
            for r in results:
                if r.stock == stock:
                    sorted_results.append(r)
                    break
        return sorted_results
