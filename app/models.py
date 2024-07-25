from datetime import datetime
from typing import List

from pydantic import BaseModel


class MarketCap(BaseModel):
    currency: str
    value: float


class Competitor(BaseModel):
    name: str
    company_code: str
    percent_change: float
    market_cap: MarketCap

    def to_dict(self):
        return {
            "name": self.name,
            "company_code": self.company_code,
            "percent_change": self.percent_change,
            "market_cap": {
                "value": self.market_cap.value,
                "currency": self.market_cap.currency,
            },
        }


class PerformanceData(BaseModel):
    date_time: datetime
    five_days: float
    one_month: float
    three_months: float
    year_to_date: float
    one_year: float
    company_code: str

    def to_dict(self):
        return {
            "five_days": self.five_days,
            "one_month": self.one_month,
            "three_months": self.three_months,
            "year_to_date": self.year_to_date,
            "one_year": self.one_year,
            "date_time": self.date_time.strftime("%Y-%m-%d %H:%M:%S"),
            "company_code": self.company_code,
        }


class StockValues(BaseModel):
    open: float
    high: float
    low: float
    close: float


class Stock(BaseModel):
    status: str
    purchased_amount: int
    purchased_status: str
    request_date: str
    company_code: str
    company_name: str
    stock_values: StockValues
    performance_data: List[PerformanceData]
    competitors: List[Competitor]

    def to_dict(self):
        return {
            "status": self.status,
            "purchased_amount": self.purchased_amount,
            "purchased_status": self.purchased_status,
            "request_date": self.request_date,
            "company_code": self.company_code,
            "company_name": self.company_name,
            "stock_values": {
                "open": self.stock_values.open,
                "high": self.stock_values.high,
                "low": self.stock_values.low,
                "close": self.stock_values.close,
            },
            "performance_data": [p.to_dict() for p in self.performance_data],
            "competitors": [c.to_dict() for c in self.competitors],
        }
