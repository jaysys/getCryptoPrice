import os
from typing import Union, Dict, List, Tuple
from dataclasses import dataclass
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

@dataclass
class ExchangePrice:
    exchange: str
    price: float
    error: str = None

    @property
    def is_error(self) -> bool:
        return self.error is not None

@dataclass
class CryptoHolding:
    symbol: str
    amount: float

@dataclass
class PortfolioItem:
    symbol: str
    amount: float
    price: float
    exchange: str
    total_value: float

class PriceAPI:
    def __init__(self):
        self.token_map = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "sol": "solana",
            "xrp": "ripple",
            "ada": "cardano",
            "doge": "dogecoin",
            "link": "chainlink",
            "uni": "uniswap",
            "ai16z": "ai16z",
            "virtual": "virtual-protocol",
            "sui": "sui",
            "fet": "fetch-ai",
            "usdc": "usd-coin",
            "usdt": "tether",
        }

    def _make_request(self, url: str) -> Union[Dict, str]:
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return f"Error: {str(e)}"

    def get_upbit_price(self, coin: str) -> ExchangePrice:
        if coin.lower() == 'krw':
            return ExchangePrice("Upbit", 1.0)

        url = f'https://api.upbit.com/v1/ticker?markets=KRW-{coin.upper()}'
        data = self._make_request(url)

        if isinstance(data, str):
            return ExchangePrice("Upbit", 0.0, data)

        if data and len(data) > 0:
            try:
                return ExchangePrice("Upbit", float(data[0].get("trade_price", 0)))
            except (ValueError, TypeError):
                return ExchangePrice("Upbit", 0.0, "Error: Invalid price data")
        return ExchangePrice("Upbit", 0.0, "Error: Empty response from API")

    def get_bithumb_price(self, coin: str) -> ExchangePrice:
        if coin.lower() == 'krw':
            return ExchangePrice("Bithumb", 1.0)

        url = f'https://api.bithumb.com/public/ticker/{coin}_KRW'
        data = self._make_request(url)

        if isinstance(data, str):
            return ExchangePrice("Bithumb", 0.0, data)

        if data.get("status") == "0000":
            try:
                return ExchangePrice("Bithumb", float(data["data"].get("closing_price", 0)))
            except (ValueError, TypeError):
                return ExchangePrice("Bithumb", 0.0, "Error: Invalid price data")
        return ExchangePrice("Bithumb", 0.0, f"Error: API returned status {data.get('status')}")

    def get_coinone_price(self, coin: str) -> ExchangePrice:
        if coin.lower() == 'krw':
            return ExchangePrice("Coinone", 1.0)

        url = f'https://api.coinone.co.kr/ticker/?currency={coin}'
        data = self._make_request(url)

        if isinstance(data, str):
            return ExchangePrice("Coinone", 0.0, data)

        if data.get("errorCode") == "0":
            try:
                return ExchangePrice("Coinone", float(data.get("last", 0)))
            except (ValueError, TypeError):
                return ExchangePrice("Coinone", 0.0, "Error: Invalid price data")
        return ExchangePrice("Coinone", 0.0, f"Error: API returned errorCode {data.get('errorCode')}")

    def get_coingecko_price(self, coin: str) -> ExchangePrice:
        if coin.lower() == 'krw':
            return ExchangePrice("Coingecko", 1.0)

        token_id = self.token_map.get(coin.lower(), coin.lower())
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={token_id}&vs_currencies=krw'
        data = self._make_request(url)

        if isinstance(data, str):
            return ExchangePrice("Coingecko", 0.0, data)

        try:
            price = data.get(token_id, {}).get('krw', 0)
            return ExchangePrice("Coingecko", float(price))
        except (ValueError, TypeError):
            return ExchangePrice("Coingecko", 0.0, f"Error: Unable to get price for {coin}")

class PortfolioManager:
    def __init__(self):
        self.api = PriceAPI()
        self.holdings: List[CryptoHolding] = []
        self.load_holdings()

    def load_holdings(self):
        """Load holdings from .env file"""
        load_dotenv()
        
        self.holdings = []
        
        for key, value in os.environ.items():
            if key.startswith('CRYPTO_'):
                symbol = key.split('_')[1].lower()
                try:
                    amount = float(value)
                    self.holdings.append(CryptoHolding(symbol, amount))
                except ValueError:
                    print(f"Warning: Invalid amount for {symbol}: {value}")

    def get_first_valid_price(self, symbol: str) -> Tuple[float, str]:
        """Get the first valid price from exchanges in priority order"""
        exchanges = [
            (self.api.get_upbit_price, "Upbit"),
            (self.api.get_bithumb_price, "Bithumb"),
            (self.api.get_coinone_price, "Coinone"),
            (self.api.get_coingecko_price, "Coingecko")
        ]

        for get_price, exchange_name in exchanges:
            result = get_price(symbol)
            if not result.is_error and result.price > 0:
                return result.price, exchange_name

        return 0.0, "No valid price found"
 
 

    def calculate_portfolio(self) -> pd.DataFrame:
        """Calculate portfolio values and return as DataFrame"""
        portfolio_data = []
        total_value = 0.0
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for holding in self.holdings:
            price, exchange = self.get_first_valid_price(holding.symbol)
            total_holding_value = price * holding.amount
            total_value += total_holding_value

            portfolio_data.append({
                "Time": current_time,
                "Symbol": holding.symbol.upper(),
                "Amount": holding.amount,
                "Price (KRW)": price,
                "Exchange": exchange,
                "Total Value (KRW)": total_holding_value
            })

        # Create DataFrame without total row
        df = pd.DataFrame(portfolio_data)

        # 'Total Value (KRW)' 기준 내림차순 정렬 + 인덱스 초기화
        df = df.sort_values(by="Total Value (KRW)", ascending=False).reset_index(drop=True)

        # Add total row after sorting
        total_row = pd.DataFrame([{
            "Time": current_time,
            "Symbol": "TOTAL",
            "Amount": pd.NA,
            "Price (KRW)": pd.NA,
            "Exchange": pd.NA,
            "Total Value (KRW)": total_value
        }])

        # Concatenate sorted data with total row
        df = pd.concat([df, total_row], ignore_index=True)
        
        # Ensure correct column order
        columns = ["Time", "Symbol", "Amount", "Price (KRW)", "Exchange", "Total Value (KRW)"]
        df = df[columns]
        
        return df


def main():
    # Set display options
    pd.options.display.float_format = '{:,.2f}'.format
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)

    # Initialize and run portfolio manager
    portfolio_manager = PortfolioManager()
    portfolio_df = portfolio_manager.calculate_portfolio()
    
    print("[ Cryptocurrency Portfolio ]")
    print(portfolio_df)

if __name__ == "__main__":
    main()

 
