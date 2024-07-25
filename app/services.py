import logging
import os
import re
from datetime import datetime
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.client import ClientOptions

from app.models import Competitor, MarketCap, PerformanceData, Stock, StockValues

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
POLYGON_BASE_URL = os.getenv("POLYGON_BASE_URL")
ZENROW_API_KEY = os.getenv("ZENROW_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# This client is an API with the Postgres db
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(
        postgrest_client_timeout=10,
        storage_client_timeout=10,
        schema="public",
    ),
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=100)
def get_stock_data(stock_symbol, date):
    logger.info(f"Fetching stock data for symbol: {stock_symbol} on date: {date}")

    lower_stock_symbol = stock_symbol.lower()
    polygon_url = f"{POLYGON_BASE_URL}/v1/open-close/{stock_symbol}/{date}?apiKey={POLYGON_API_KEY}"
    response = requests.get(polygon_url).json()
    # Check if data is not found in polygon for the specified date to avoid scraping for unavailable dates
    if response.get("status") == "NOT_FOUND":
        return {
            "message": f"Data unavailable for stock {stock_symbol} on date {date}.",
            "info": "Please check the available dates and stock symbols.",
            "polygon_docs": "https://polygon.io/docs/stocks/get_v1_open-close__stockscompany_code___date",
            "marketwatch_company_codes": "https://www.marketwatch.com/tools/markets/stocks/country/united-states",
        }
    stock_values = StockValues(
        open=response["open"],
        high=response["high"],
        low=response["low"],
        close=response["close"],
    )

    marketwatch_url = f"https://www.marketwatch.com/investing/stock/{lower_stock_symbol}?mod=u.s.-market-data"
    #  Headers avoid dynamic loading blockers like Captcha
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    try:
        response = requests.get(marketwatch_url, headers=headers)
    except Exception as e:
        logger.error(f"Error fetching MarketWatch data: {e}")
        # Fallback to ZenRows if initial request fails
        response = requests.get(
            "https://api.zenrows.com/v1/",
            params={
                "url": marketwatch_url,
                "apikey": ZENROW_API_KEY,
                "js_render": "true",
                "wait_for": "column--aside",
                "premium_proxy": "true",
                "wait": "15",
            },
        )

    soup = BeautifulSoup(response.text, "html.parser")

    company_name_element = soup.find("h1", {"class": "company__name"})
    company_name = (
        company_name_element.text.strip() if company_name_element else "Unknown"
    )

    performance_table = soup.find("div", {"class": "performance"})
    competitor_table = soup.find("div", {"class": "Competitors"})

    performance_data = extract_performance_data(performance_table, stock_symbol)
    competitors = extract_competitors_data(competitor_table)

    stock_data = Stock(
        status="active",
        purchased_status="confirmed",
        purchased_amount=0,
        request_date=date,
        company_code=stock_symbol,
        company_name=company_name,
        stock_values=stock_values,
        performance_data=performance_data,
        competitors=competitors,
    )
    #  Persist data to Supabase
    try:
        persisted_stock = persist_stock_data(stock_data, performance_data, competitors)
    except Exception as e:
        logger.error(f"Error persisting data to db: {e}")
        return stock_data.to_dict()
    return persisted_stock.to_dict()


def persist_stock_data(stock, performance_data, competitors):
    logger.info(f"Persisting stock data for symbol: {stock.company_code}")
    # first lets fetch the current amount for this stock in order to preserve it form updates that are not made through the post/stock/ route
    response = (
        supabase.table("stocks")
        .select("purchased_amount")
        .eq("company_code", stock.company_code)
        .execute()
    )
    if response.data:
        current_purchased_amount = response.data[0]["purchased_amount"]
    else:
        current_purchased_amount = stock.purchased_amount

    result = (
        supabase.table("stocks")
        .upsert(
            {
                "status": stock.status,
                "purchased_amount": current_purchased_amount,
                "purchased_status": stock.purchased_status,
                "request_date": stock.request_date,
                "company_code": stock.company_code,
                "company_name": stock.company_name,
                "open": stock.stock_values.open,
                "high": stock.stock_values.high,
                "low": stock.stock_values.low,
                "close": stock.stock_values.close,
            },
            on_conflict=["company_code"],
        )
        .execute()
    )
    logger.debug(f"Persist stock result: {result}")
    for perf_data in performance_data:
        supabase.table("performance_data").upsert(
            {
                "company_code": stock.company_code,
                "date_time": perf_data.date_time.isoformat(),
                "five_days": perf_data.five_days,
                "one_month": perf_data.one_month,
                "three_months": perf_data.three_months,
                "year_to_date": perf_data.year_to_date,
                "one_year": perf_data.one_year,
            },
            on_conflict=["company_code"],
        ).execute()

    for competitor in competitors:
        supabase.table("competitors").upsert(
            {
                "company_code": competitor.company_code,
                "name": competitor.name,
                "percent_change": competitor.percent_change,
                "market_cap_value": competitor.market_cap.value,
                "market_cap_currency": competitor.market_cap.currency,
            },
            on_conflict=["company_code"],
        ).execute()

    persisted_stock = Stock(
        status=stock.status,
        purchased_amount=current_purchased_amount,
        purchased_status=stock.purchased_status,
        request_date=stock.request_date,
        company_code=stock.company_code,
        company_name=stock.company_name,
        stock_values=stock.stock_values,
        performance_data=performance_data,
        competitors=competitors,
    )
    return persisted_stock


def extract_performance_data(column, company_code):
    logger.info(f"Extracting performance data for symbol: {company_code}")

    performance_data = []
    rows = column.find_all("tr", {"class": "table__row"})
    data = {
        "five_days": 0.0,
        "one_month": 0.0,
        "three_months": 0.0,
        "year_to_date": 0.0,
        "one_year": 0.0,
        "date_time": datetime.now(),
    }
    for row in rows:
        label = row.find("td", {"class": "table__cell"}).text.strip()
        value = float(
            row.find("li", {"class": "content__item value ignore-color"}).text.strip(
                "%"
            )
        )
        if label == "5 Day":
            data["five_days"] = value
        elif label == "1 Month":
            data["one_month"] = value
        elif label == "3 Month":
            data["three_months"] = value
        elif label == "YTD":
            data["year_to_date"] = value
        elif label == "1 Year":
            data["one_year"] = value
    data["company_code"] = company_code
    performance_data.append(PerformanceData(**data))
    return performance_data


def extract_competitors_data(competitor_table):
    logger.info("Extracting competitors data")

    competitors = []
    rows = competitor_table.find_all("tr", {"class": "table__row"})
    for row in rows:
        name_cell = row.find("td", {"class": "table__cell w50"})
        if name_cell:
            company_name = name_cell.text.strip()
            company_code = (
                name_cell.find("a", href=True)["href"].split("/")[-1].split("?")[0]
            )
            percent_change = float(
                row.find("td", {"class": "table__cell w25"})
                .find("bg-quote")
                .text.strip("%")
            )
            market_cap_text = row.find(
                "td", {"class": "table__cell w25 number"}
            ).text.strip()
            market_cap_value, market_cap_currency = parse_market_cap(market_cap_text)

            competitors.append(
                Competitor(
                    name=company_name,
                    company_code=company_code,
                    percent_change=percent_change,
                    market_cap=MarketCap(
                        value=market_cap_value, currency=market_cap_currency
                    ),
                )
            )

    return competitors


def parse_market_cap(text):
    currency_symbols = {
        "$": "USD",
        "€": "EUR",
        "R$": "BRL",
        "¥": "JPY",
        "£": "GBP",
        "A$": "AUD",
        "C$": "CAD",
        "CHF": "CHF",
        "CN¥": "CNY",
        "₹": "INR",
    }

    currency_symbol = re.match(r"[^\d]+", text).group().strip()
    currency = currency_symbols.get(currency_symbol, "USD")
    text = text.replace(currency_symbol, "").strip()

    if "T" in text:
        return float(text.strip("T")) * 1e12, currency
    elif "B" in text:
        return float(text.strip("B")) * 1e9, currency
    elif "M" in text:
        return float(text.strip("M")) * 1e6, currency
    return float(text), currency


def update_stock_amount(stock_symbol, amount):
    stock_symbol = stock_symbol.upper()

    # Fetch current amount to enable adding
    response = (
        supabase.table("stocks")
        .select("company_code, purchased_amount, id")
        .eq("company_code", stock_symbol)
        .execute()
    )

    if response.data:
        current_amount = response.data[0]["purchased_amount"]
        stock_id = response.data[0]["id"]
    else:
        current_amount = 0
        stock_id = None

    new_amount = current_amount + amount
    if new_amount < 0:
        new_amount = 0

    if stock_id:
        # Update stock amount
        response = (
            supabase.table("stocks")
            .update({"purchased_amount": new_amount})
            .eq("id", stock_id)
            .execute()
        )
    else:
        # Insert new stock record if it doesn't exist
        response = (
            supabase.table("stocks")
            .insert({"company_code": stock_symbol, "purchased_amount": new_amount})
            .execute()
        )

    updated_response = (
        supabase.table("stocks")
        .select("company_code, purchased_amount")
        .eq("id", stock_id)
        .execute()
    )

    if not updated_response.data:
        logger.error(f"Error fetching updated stock amount: {updated_response}")
        return {"success": False, "error": "Error fetching updated stock amount"}

    return {"success": True, "data": updated_response.data[0]}
