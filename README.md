# 주식 데이터베이스 관리 시스템

한국 및 미국 주식 데이터를 자동으로 수집하고 DuckDB 데이터베이스로 관리하는 시스템입니다.

## 📁 파일 구조

```
DATABASE/
├── README.md                 # 이 파일
├── tickergenerator.py        # 주식 티커 코드 생성기
├── create_kr_db.py          # 한국 주식 DB 생성/업데이트
├── create_us_db.py          # 미국 주식 DB 생성/업데이트
├── convert2csv.py           # Discord 알림 테스트 도구
├── cron.txt                 # 크론 작업 설정 메모
├── KrStockCodeList.json     # 한국 주식 티커 목록
├── UsStockCodeList.json     # 미국 주식 티커 목록
├── kr.db                    # 한국 주식 DuckDB 데이터베이스
├── us.db                    # 미국 주식 DuckDB 데이터베이스
└── stock.db                 # 통합 주식 데이터베이스
```

## 🚀 주요 기능

### 1. 티커 코드 생성 (`tickergenerator.py`)
- **한국 주식**: KOSPI/KOSDAQ 티커를 `.KS`/`.KQ` 접미사와 함께 수집
- **미국 주식**: NASDAQ/NYSE/AMEX 거래소의 모든 주식 티커 수집
- **다중 소스**: pykrx와 FinanceDataReader를 활용한 안정적인 데이터 수집
- **자동 필터링**: 유효하지 않은 티커 제거 및 중복 제거

### 2. 데이터베이스 생성/업데이트
- **한국 주식** (`create_kr_db.py`): 한국 주식 데이터를 `kr.db`에 저장
- **미국 주식** (`create_us_db.py`): 미국 주식 데이터를 `us.db`에 저장
- **증분 업데이트**: 기존 데이터가 있으면 새로운 날짜만 추가
- **중복 방지**: 동일 날짜 데이터가 있으면 자동으로 스킵

### 3. 수집 데이터 항목
- **OHLCV 데이터**: Open, High, Low, Close, Volume, Adj Close
- **거래대금**: Close × Volume 자동 계산
- **재무 정보**: 시가총액, PER, PBR, 배당수익률 등 40+ 지표
- **ETF 정보**: ETF의 경우 별도 지표 수집 -예정정

## 📋 필요 라이브러리

```bash
pip install yfinance>=0.2.18
pip install Finance-DataReader>=0.9.50
pip install pykrx>=1.0.36
pip install pandas>=1.5.0
pip install duckdb>=0.9.0
pip install numpy>=1.24.0
pip install requests>=2.31.0
```

## 🔧 사용법

### 1. 티커 코드 생성
```bash
# 한국 및 미국 주식 티커 코드 생성
python tickergenerator.py
```

### 2. 데이터베이스 업데이트
```bash
# 한국 주식 DB 업데이트 (오늘 날짜)
python create_kr_db.py

# 미국 주식 DB 업데이트 (어제 날짜)
python create_us_db.py

# 특정 날짜로 업데이트
python create_kr_db.py --date 2026-01-03
python create_us_db.py --date 2026-01-03

# Discord 웹훅으로 알림 받기
python create_kr_db.py --webhook YOUR_WEBHOOK_URL
```

## 📊 데이터베이스 스키마

### stock_data 테이블
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| Date | STRING | 거래일 (YYYY-MM-DD) |
| Ticker | STRING | 주식 티커 (예: 005930.KS, AAPL) |
| Open | FLOAT | 시가 |
| High | FLOAT | 고가 |
| Low | FLOAT | 저가 |
| Close | FLOAT | 종가 |
| Volume | INTEGER | 거래량 |
| VolumeMoney | FLOAT | 거래대금 (Close × Volume) |
| Adj Close | FLOAT | 수정종가 |
| marketCap | FLOAT | 시가총액 |
| dividendYield | FLOAT | 배당수익률 |
| trailingPE | FLOAT | PER |
| priceToBook | FLOAT | PBR |
| ... | ... | 기타 40+ 재무지표 |

## 🔄 자동화 설정

### Cron 작업 예시
```bash
# 매일 오전 9시에 티커 코드 업데이트
0 9 * * 1-5 cd /path/to/DATABASE && python tickergenerator.py

# 매일 오후 5시에 한국 주식 DB 업데이트
0 17 * * 1-5 cd /path/to/DATABASE && python create_kr_db.py

# 매일 오전 7시에 미국 주식 DB 업데이트 D+1
0 7 * * 2-6 cd /path/to/DATABASE && python create_us_db.py
```

## 📱 Discord 알림

시스템은 Discord 웹훅을 통해 다음 상황에서 알림을 전송합니다:
- 데이터 수집 시작/완료
- 오류 발생
- 데이터 수집 통계 (성공률, 소요시간 등)

## ⚠️ 주의사항

1. **API 제한**: yfinance API 호출 제한을 고려하여 배치 처리 및 지연 시간 설정
2. **영업일**: 주말이나 공휴일에는 데이터가 없을 수 있음
3. **네트워크**: 안정적인 인터넷 연결 필요
4. **디스크 공간**: 대량의 주식 데이터 저장을 위한 충분한 저장 공간 필요

## 🐛 문제 해결

### 한국 주식 데이터 수집 실패
- pykrx 라이브러리 업데이트: `pip install --upgrade pykrx`
- FinanceDataReader 대체 사용: 자동으로 fallback 처리됨

### 미국 주식 데이터 수집 실패
- yfinance 라이브러리 업데이트: `pip install --upgrade yfinance`
- API 호출 간격 조정: `DELAY_SECONDS` 값 증가

### 데이터베이스 오류
- DuckDB 파일 권한 확인
- 디스크 공간 확인
- 기존 DB 파일 백업 후 재생성

## 📈 성능 최적화

- **배치 크기**: `BATCH_SIZE = 80` (API 호출 제한 고려)
- **지연 시간**: `DELAY_SECONDS = 1` (서버 부하 방지)
- **진행률 표시**: 100개마다 진행 상황 출력
- **메모리 관리**: 대용량 데이터 처리를 위한 배치 처리

## 📝 로그 및 모니터링

- 콘솔 출력을 통한 실시간 진행 상황 확인
- Discord 알림을 통한 원격 모니터링
- 성공/실패 통계 자동 집계
- 예상 완료 시간 계산 및 표시

---

**개발자**: 주식 데이터 수집 시스템  
**최종 업데이트**: 2026년 1월  
**라이선스**: MIT
