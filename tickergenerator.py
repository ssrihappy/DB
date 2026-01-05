# -*- coding: utf-8 -*-

# 1일 1회 월-토 실행


# Python 3.14 호환성 및 경고 해결
import warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='pkg_resources is deprecated')

# pkg_resources 호환성 패치
import sys
if sys.version_info >= (3, 12):
    try:
        import pkg_resources
    except ImportError:
        import importlib.metadata as pkg_resources
        sys.modules['pkg_resources'] = pkg_resources

import json
import time
import requests
from datetime import datetime, timedelta

DISCORD_WEBHOOK_URL = 'URL'

def send_discord_notification(message: str, webhook_url: str = None):
    """Discord 웹훅으로 알림 전송"""
    if not webhook_url and not DISCORD_WEBHOOK_URL:
        return
    
    url = webhook_url or DISCORD_WEBHOOK_URL
    
    try:
        payload = {
            "content": message,
            "username": "DB logger",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2857/2857401.png"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 204:
            print("Discord 알림 전송 완료")
        else:
            print(f"Discord 알림 전송 실패: {response.status_code}")
    except Exception as e:
        print(f"Discord 알림 전송 중 오류: {e}")

# 안전한 모듈 임포트
try:
    import FinanceDataReader as fdr
    FDR_AVAILABLE = True
    print("FinanceDataReader 사용 가능")
except ImportError:
    FDR_AVAILABLE = False
    print("FinanceDataReader 사용 불가")

try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
    print("pykrx 사용 가능")
except ImportError:
    PYKRX_AVAILABLE = False
    print("pykrx 사용 불가")

def safe_fdr_call(market, max_retries=3):
    """안전한 FDR 호출"""
    for attempt in range(max_retries):
        try:
            print(f"FDR {market} 시도 {attempt + 1}/{max_retries}")
            time.sleep(2 * (attempt + 1))  # 점진적 대기
            
            df = fdr.StockListing(market)
            if df is not None and len(df) > 0:
                print(f"FDR {market} 성공: {len(df)}개")
                return df
            else:
                print(f"FDR {market} 빈 데이터")
                
        except Exception as e:
            print(f"FDR {market} 시도 {attempt + 1} 실패: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
    
    return None

def safe_pykrx_call(market, date_str=None, max_retries=3):
    """안전한 pykrx 호출"""
    for attempt in range(max_retries):
        try:
            print(f"pykrx {market} 시도 {attempt + 1}/{max_retries} (날짜: {date_str or '없음'})")
            
            if date_str:
                result = stock.get_market_ticker_list(date=date_str, market=market)
            else:
                result = stock.get_market_ticker_list(market=market)
            
            if result and len(result) > 0:
                print(f"pykrx {market} 성공: {len(result)}개")
                return result
            else:
                print(f"pykrx {market} 빈 데이터")
                
        except Exception as e:
            print(f"pykrx {market} 시도 {attempt + 1} 실패: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
            continue
    
    return []

def get_korea_stocks():
    """한국 주식 코드 가져오기 - 다중 방법"""
    korea_stocks = []
    success_method = None
    
    # 방법 1: pykrx 시도 (최근 영업일들)
    if PYKRX_AVAILABLE:
        print("=== pykrx 방법 시도 ===")
        
        # 최근 영업일 찾기
        today = datetime.now()
        business_dates = []
        for i in range(15):  # 최근 15일
            date = today - timedelta(days=i)
            if date.weekday() < 5:  # 주말 제외
                business_dates.append(date.strftime('%Y%m%d'))
        
        for date_str in business_dates[:5]:  # 최근 5개 영업일만 시도
            kospi_list = safe_pykrx_call("KOSPI", date_str)
            kosdaq_list = safe_pykrx_call("KOSDAQ", date_str)
            
            if len(kospi_list) > 0 or len(kosdaq_list) > 0:
                # 접미사 추가
                kospi_formatted = [ticker + ".KS" for ticker in kospi_list]
                kosdaq_formatted = [ticker + ".KQ" for ticker in kosdaq_list]
                korea_stocks = kospi_formatted + kosdaq_formatted
                
                print(f"pykrx 성공 ({date_str}): 총 {len(korea_stocks)}개")
                if len(korea_stocks) >= 1000:
                    success_method = f"pykrx ({date_str})"
                    break
        
        # 날짜 없이 시도
        if len(korea_stocks) < 1000:
            kospi_list = safe_pykrx_call("KOSPI")
            kosdaq_list = safe_pykrx_call("KOSDAQ")
            
            if len(kospi_list) > 0 or len(kosdaq_list) > 0:
                kospi_formatted = [ticker + ".KS" for ticker in kospi_list]
                kosdaq_formatted = [ticker + ".KQ" for ticker in kosdaq_list]
                korea_stocks = kospi_formatted + kosdaq_formatted
                
                if len(korea_stocks) >= 1000:
                    success_method = "pykrx (날짜없음)"
    
    # 방법 2: FinanceDataReader 시도
    if len(korea_stocks) < 1000 and FDR_AVAILABLE:
        print("=== FinanceDataReader 방법 시도 ===")
        
        # 개별 시장 시도
        df_kospi = safe_fdr_call('KOSPI')
        df_kosdaq = safe_fdr_call('KOSDAQ')
        
        if df_kospi is not None or df_kosdaq is not None:
            fdr_stocks = []
            
            if df_kospi is not None:
                print("KOSPI columns:", df_kospi.columns.tolist())
                kospi_col = 'Code' if 'Code' in df_kospi.columns else df_kospi.columns[0]
                kospi_codes = [str(code) + ".KS" for code in df_kospi[kospi_col].tolist()]
                fdr_stocks.extend(kospi_codes)
            
            if df_kosdaq is not None:
                print("KOSDAQ columns:", df_kosdaq.columns.tolist())
                kosdaq_col = 'Code' if 'Code' in df_kosdaq.columns else df_kosdaq.columns[0]
                kosdaq_codes = [str(code) + ".KQ" for code in df_kosdaq[kosdaq_col].tolist()]
                fdr_stocks.extend(kosdaq_codes)
            
            # 필터링
            filtered_stocks = []
            for stock_code in fdr_stocks:
                base_ticker = stock_code.split('.')[0]
                if (len(base_ticker) == 6 and 
                    (base_ticker.isdigit() or base_ticker[:-1].isdigit()) and
                    stock_code not in filtered_stocks):
                    filtered_stocks.append(stock_code)
            
            if len(filtered_stocks) > len(korea_stocks):
                korea_stocks = filtered_stocks
                success_method = "FinanceDataReader"
                print(f"FDR 성공: {len(korea_stocks)}개")
    
    return korea_stocks, success_method

def get_us_stocks():
    """미국 주식 코드 가져오기"""
    if not FDR_AVAILABLE:
        return []
    
    print("=== 미국 주식 코드 수집 ===")
    
    us_stocks = []
    markets = ['NASDAQ', 'NYSE', 'AMEX']
    
    for market in markets:
        df = safe_fdr_call(market)
        if df is not None:
            print(f"{market} columns:", df.columns.tolist())
            symbol_col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            symbols = df[symbol_col].tolist()
            us_stocks.extend(symbols)
    
    # 필터링: 공백이나 점이 없는 심볼만, 중복 제거
    filtered_us = []
    for symbol in us_stocks:
        if (isinstance(symbol, str) and 
            ' ' not in symbol and '.' not in symbol and 
            symbol not in filtered_us):
            filtered_us.append(symbol)
    
    print(f"미국 주식 필터링 결과: {len(filtered_us)}개")
    return filtered_us

def main():
    print("주식 코드 수집 시작...")
    
    # 한국 주식 수집
    korea_stocks, method = get_korea_stocks()
    
    if len(korea_stocks) > 0:
        print(f"한국 주식 수집 성공: {len(korea_stocks)}개 ({method})")        
    else:
        print("한국 주식 수집 실패")
        korea_stocks = []
    
    # 한국 주식 저장
    korea_file_path = "./KrStockCodeList.json"
    try:
        with open(korea_file_path, 'w', encoding='utf-8') as outfile:
            json.dump(korea_stocks, outfile, ensure_ascii=False, indent=2)
        msg = f"한국 주식 코드 저장 완료: {len(korea_stocks)}개"
        print(msg)
        send_discord_notification(msg, DISCORD_WEBHOOK_URL)
    except Exception as e:
        print(f"한국 주식 저장 에러: {e}")
    
    print("##########################################################")
    
    # 미국 주식 수집
    us_stocks = get_us_stocks()
    
    # 미국 주식 저장
    us_file_path = "./UsStockCodeList.json"
    try:
        with open(us_file_path, 'w', encoding='utf-8') as outfile:
            json.dump(us_stocks, outfile, ensure_ascii=False, indent=2)
        msg2 = f"미국 주식 코드 저장 완료: {len(us_stocks)}개"
        send_discord_notification(msg2, DISCORD_WEBHOOK_URL)

    except Exception as e:
        print(f"미국 주식 저장 에러: {e}")
    
    # 최종 결과
    print(f"\n=== 최종 결과 ===")
    print(f"한국 주식: {len(korea_stocks)}개")
    print(f"미국 주식: {len(us_stocks)}개")
    
    if len(korea_stocks) >= 1000:
        print("✅ 한국 주식 수집 성공!")
    else:
        print("⚠️ 한국 주식 수집 부족")
    
    if len(us_stocks) >= 1000:
        print("✅ 미국 주식 수집 성공!")
    else:
        print("⚠️ 미국 주식 수집 부족")

if __name__ == "__main__":
    main()