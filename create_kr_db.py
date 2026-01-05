# -*- coding: utf-8 -*-
"""
US 주식 데이터베이스 생성 도구

UsStockCodeList.json의 티커를 읽어서 us.db 생성
- us.db가 없으면 새로 생성
- us.db가 있으면 불러와서 데이터 추가
- 동일 날짜 데이터가 있으면 스킵
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import pandas as pd
import yfinance as yf
import duckdb
import requests




# ==================== 설정 ====================
TICKER_LIST_PATH = "KrStockCodeList.json"

# Discord 웹훅 설정 (환경변수 또는 직접 설정)
DISCORD_WEBHOOK_URL = 'URL'
DB_PATH = "kr.db"

# API 호출 제한 설정
BATCH_SIZE = 80  # 몇 개마다 sleep
DELAY_SECONDS = 1  # sleep 시간(초)
LOG_INTERVAL = 100  # 진행률 표시 간격

# 재무 정보 키 리스트
EQUITY_INFO_KEYS = [
    'marketCap', 'dividendYield', 'payoutRatio', 'beta', 'trailingPE', 'forwardPE',
    'priceToSalesTrailing12Months', 'trailingAnnualDividendYield', 'enterpriseValue',
    'profitMargins', 'floatShares', 'sharesOutstanding', 'sharesShort',
    'dateShortInterest', 'sharesPercentSharesOut', 'heldPercentInsiders',
    'heldPercentInstitutions', 'shortRatio', 'shortPercentOfFloat', 'bookValue',
    'priceToBook', 'earningsQuarterlyGrowth', 'netIncomeToCommon', 'trailingEps',
    'forwardEps', 'pegRatio', 'enterpriseToRevenue', 'enterpriseToEbitda',
    'lastDividendValue', 'shortName', 'totalCash', 'totalCashPerShare', 'ebitda',
    'totalDebt', 'quickRatio', 'currentRatio', 'totalRevenue', 'debtToEquity',
    'revenuePerShare', 'returnOnAssets', 'returnOnEquity', 'freeCashflow',
    'operatingCashflow', 'earningsGrowth', 'revenueGrowth', 'grossMargins',
    'ebitdaMargins', 'operatingMargins', 'trailingPegRatio', 'fullTimeEmployees',
    'quoteType'
]

ETF_INFO_KEYS = ['yield', 'totalAssets', 'navPrice', 'shortName', 'quoteType']
ALL_INFO_KEYS = list(set(EQUITY_INFO_KEYS + ETF_INFO_KEYS))


# ==================== 유틸리티 함수 ====================
def safe_convert_numeric(value, data_type='float'):
    """안전한 숫자 변환"""
    try:
        if pd.isna(value) or value is None:
            return None
        if data_type == 'float':
            return float(value)
        elif data_type == 'int':
            return int(value)
        return value
    except (ValueError, TypeError, OverflowError):
        return None


def read_ticker_list(file_path: str = TICKER_LIST_PATH) -> List[str]:
    """티커 리스트 JSON 파일 읽기"""
    with open(file_path, 'r', encoding='utf-8') as f:
        tickers = json.load(f)
    return tickers


def send_discord_notification(message: str, webhook_url: str = None):
    """Discord 웹훅으로 알림 전송"""
    if not webhook_url and not DISCORD_WEBHOOK_URL:
        return
    
    url = webhook_url or DISCORD_WEBHOOK_URL
    
    try:
        payload = {
            "content": message,
            "username": "DB logger(KR)",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2857/2857401.png"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 204:
            print("Discord 알림 전송 완료")
        else:
            print(f"Discord 알림 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"Discord 알림 전송 중 오류: {e}")

# ==================== DB 관리 ====================
class DatabaseManager:
    """DuckDB 데이터베이스 관리"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """DB 연결"""
        if self.conn is None:
            self.conn = duckdb.connect(self.db_path)
        return self.conn

    def close(self):
        """DB 연결 종료"""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def table_exists(self, table_name: str = "stock_data") -> bool:
        """테이블 존재 여부 확인"""
        try:
            conn = self.connect()
            result = conn.execute(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'"
            ).fetchone()
            return result[0] > 0 if result else False
        except Exception:
            return False

    def get_date_count(self, date_str: str) -> int:
        """특정 날짜의 데이터 개수 조회"""
        try:
            conn = self.connect()
            result = conn.execute(
                f"SELECT COUNT(*) FROM stock_data WHERE Date = '{date_str}'"
            ).fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def create_table(self, df: pd.DataFrame):
        """테이블 생성"""
        conn = self.connect()
        conn.execute("DROP TABLE IF EXISTS stock_data")
        conn.execute("CREATE TABLE stock_data AS SELECT * FROM df")

    def insert_dataframe(self, df: pd.DataFrame):
        """데이터 삽입"""
        conn = self.connect()
        columns = self.get_columns()
        df = df.reindex(columns=columns)
        column_list = ', '.join([f'"{col}"' for col in columns])
        conn.execute(f"INSERT INTO stock_data ({column_list}) SELECT {column_list} FROM df")

    def get_columns(self) -> List[str]:
        """테이블 컬럼 목록 조회"""
        conn = self.connect()
        result = conn.execute("PRAGMA table_info(stock_data)").fetchall()
        return [col[1] for col in result]

    def get_latest_date(self) -> Optional[str]:
        """최신 날짜 조회"""
        try:
            conn = self.connect()
            result = conn.execute("SELECT MAX(Date) FROM stock_data").fetchone()
            return result[0] if result else None
        except Exception:
            return None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ==================== 데이터 수집 ====================
def get_ticker_data(ticker: str, date_str: str) -> Optional[pd.DataFrame]:
    """
    단일 티커의 OHLCV 및 재무 데이터 수집

    Args:
        ticker: 티커 심볼
        date_str: 날짜 (YYYY-MM-DD)

    Returns:
        DataFrame 또는 None
    """
    try:
        # yfinance 티커 객체 생성
        stock = yf.Ticker(ticker)
        info_dict = stock.info

        # OHLCV 데이터 가져오기
        next_date = (datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        price_data = yf.download(
            ticker,
            start=date_str,
            end=next_date,
            progress=False,
            auto_adjust=False
        )

        if price_data.empty:
            return None

        # 멀티레벨 컬럼 처리
        if isinstance(price_data.columns, pd.MultiIndex):
            price_data.columns = price_data.columns.get_level_values(0)

        # 재무 정보 키 리스트 결정
        if info_dict.get('quoteType') == 'ETF':
            keylist_info = ETF_INFO_KEYS
        else:
            keylist_info = EQUITY_INFO_KEYS

        # 데이터 생성
        close_price = safe_convert_numeric(price_data['Close'].iloc[0] if len(price_data) > 0 else None, 'float')
        volume = safe_convert_numeric(price_data['Volume'].iloc[0] if len(price_data) > 0 else None, 'int')
        
        # 거래대금 계산 (Close * Volume)
        volume_money = None
        if close_price is not None and volume is not None:
            volume_money = close_price * volume
        
        row_data = {
            'Date': date_str,
            'Ticker': ticker,
            'Open': safe_convert_numeric(price_data['Open'].iloc[0] if len(price_data) > 0 else None, 'float'),
            'High': safe_convert_numeric(price_data['High'].iloc[0] if len(price_data) > 0 else None, 'float'),
            'Low': safe_convert_numeric(price_data['Low'].iloc[0] if len(price_data) > 0 else None, 'float'),
            'Close': close_price,
            'Volume': volume,
            'VolumeMoney': volume_money
        }

        # Adj Close 처리
        if 'Adj Close' in price_data.columns:
            row_data['Adj Close'] = safe_convert_numeric(
                price_data['Adj Close'].iloc[0] if len(price_data) > 0 else None, 'float'
            )
        else:
            row_data['Adj Close'] = close_price

        # 재무 정보 추가
        for col in ALL_INFO_KEYS:
            if col in keylist_info:
                value = info_dict.get(col, 'N/A')
                if isinstance(value, (int, float)) and not pd.isna(value):
                    row_data[col] = value
                elif value is not None and value != 'N/A':
                    row_data[col] = str(value)
                else:
                    row_data[col] = 'N/A'
            else:
                row_data[col] = 'N/A'

        # DataFrame 생성
        df = pd.DataFrame([row_data])

        # 컬럼 순서 정렬
        expected_columns = ['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume', 'VolumeMoney', 'Adj Close'] + ALL_INFO_KEYS
        available_columns = [col for col in expected_columns if col in df.columns]
        df = df[available_columns]

        return df

    except Exception as e:
        print(f"Error getting data for {ticker}: {e}")
        return None


def update_database(date_str: str, webhook_url: str = None):
    """
    특정 날짜의 데이터를 kr.db에 추가

    Args:
        date_str: 업데이트할 날짜 (YYYY-MM-DD)
        webhook_url: Discord 웹훅 URL (선택사항)
    """
    print(f"=== 한국 주식 데이터베이스 업데이트 ===")
    print(f"대상 날짜: {date_str}")
    
    # Discord 알림 - 시작
    start_message = f"🚀 **한국 주식 DB 업데이트 시작**\n📅 날짜: {date_str}\n⏰ 시작시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    send_discord_notification(start_message, webhook_url)

    # 티커 리스트 읽기
    tickers = read_ticker_list()
    print(f"티커 수: {len(tickers)}")

    # DB 연결
    db_exists = Path(DB_PATH).exists()
    db = DatabaseManager(DB_PATH)

    with db:
        # DB가 있고 해당 날짜 데이터가 있으면 스킵
        if db_exists and db.table_exists():
            print(f"기존 DB 발견: {DB_PATH}")
            existing_count = db.get_date_count(date_str)
            if existing_count > 0:
                skip_message = f"⚠️ **한국 주식 DB 업데이트 스킵**\n📅 날짜: {date_str}\n💾 이미 존재하는 데이터: {existing_count}개"
                send_discord_notification(skip_message, webhook_url)
                print(f"{date_str} 날짜 데이터가 이미 존재합니다 ({existing_count}개). 업데이트를 건너뜁니다.")
                return
            latest_date = db.get_latest_date()
            if latest_date:
                print(f"현재 DB 최신 날짜: {latest_date}")
        else:
            print(f"새로운 DB 생성: {DB_PATH}")

        # 데이터 수집
        new_data_list = []
        error_tickers = []
        start_time = time.time()

        print("\n데이터 수집 시작...")
        for i, ticker in enumerate(tickers):
            try:
                # 진행률 표시
                if i % LOG_INTERVAL == 0 and i > 0:
                    elapsed_time = time.time() - start_time
                    progress = round(i / len(tickers) * 100, 2)
                    
                    # 예상 완료 시간 계산
                    if i > 0:
                        avg_time_per_ticker = elapsed_time / i
                        remaining_tickers = len(tickers) - i
                        estimated_remaining_time = avg_time_per_ticker * remaining_tickers
                        
                        # 시간 포맷팅
                        elapsed_minutes = int(elapsed_time // 60)
                        elapsed_seconds = int(elapsed_time % 60)
                        remaining_minutes = int(estimated_remaining_time // 60)
                        remaining_seconds = int(estimated_remaining_time % 60)
                        
                        print(f'진행률: {progress}% ({i}/{len(tickers)}) | '
                              f'경과시간: {elapsed_minutes}분 {elapsed_seconds}초 | '
                              f'예상완료: {remaining_minutes}분 {remaining_seconds}초 후')
                    else:
                        print(f'진행률: {progress}% ({i}/{len(tickers)})')

                # API 호출 제한을 위한 지연
                if i % BATCH_SIZE == 0 and i > 0:
                    print(f"  API 제한 방지 대기 중... ({DELAY_SECONDS}초)")
                    time.sleep(DELAY_SECONDS)

                # 티커 데이터 수집
                ticker_data = get_ticker_data(ticker, date_str)

                if ticker_data is not None and not ticker_data.empty:
                    new_data_list.append(ticker_data)
                else:
                    error_tickers.append(ticker)

            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                error_tickers.append(ticker)

        if not new_data_list:
            error_message = f"❌ **한국 주식 DB 업데이트 실패**\n📅 날짜: {date_str}\n⚠️ 수집된 데이터가 없습니다."
            send_discord_notification(error_message, webhook_url)
            print("수집된 데이터가 없습니다.")
            return

        # 모든 데이터 병합
        new_df = pd.concat(new_data_list, ignore_index=True)

        # DB에 저장
        if db_exists and db.table_exists():
            db.insert_dataframe(new_df)
            print(f"\n기존 DB에 {len(new_df)}개 레코드 추가")
        else:
            db.create_table(new_df)
            print(f"\n새 DB 생성 완료: {len(new_df)}개 레코드")

        # 완료 시간 계산
        total_time = time.time() - start_time
        total_minutes = int(total_time // 60)
        total_seconds = int(total_time % 60)
        
        print(f"\n=== 업데이트 완료 ===")
        print(f"날짜: {date_str}")
        print(f"성공: {len(new_df)}개 티커")
        print(f"실패: {len(error_tickers)}개 티커")
        print(f"총 소요시간: {total_minutes}분 {total_seconds}초")
        if error_tickers:
            print(f"실패한 티커 (처음 10개): {error_tickers[:10]}")
        
        # Discord 알림 - 완료
        success_rate = round((len(new_df) / len(tickers)) * 100, 1)
        complete_message = (
            f"✅ **한국 주식 DB 업데이트 완료**\n"
            f"📅 날짜: {date_str}\n"
            f"📊 성공: {len(new_df)}개 티커 ({success_rate}%)\n"
            f"❌ 실패: {len(error_tickers)}개 티커\n"
            f"⏱️ 소요시간: {total_minutes}분 {total_seconds}초\n"
            f"🏁 완료시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_discord_notification(complete_message, webhook_url)


# ==================== 메인 ====================
def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description='US 주식 데이터베이스 생성/업데이트 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예제:
  python create_us_db.py                      # 오늘 날짜로 업데이트
  python create_us_db.py --date 2026-01-03    # 특정 날짜로 업데이트
        """
    )

    parser.add_argument(
        '--date',
        help='업데이트할 날짜 (YYYY-MM-DD, 기본값: 오늘)',
        default=datetime.now().strftime('%Y-%m-%d')
    )
    
    parser.add_argument(
        '--webhook',
        help='Discord 웹훅 URL (선택사항)',
        default=None
    )

    args = parser.parse_args()

    update_database(args.date, args.webhook)


if __name__ == '__main__':
    main()
