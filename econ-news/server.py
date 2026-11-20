"""
경제 뉴스 MCP 서버: "매일 아침 경린이의 경제신문"

  HR 저장소의 hr-news를 경제 공부용으로 바꾼 버전입니다.
  도구는 기사 목록을 가져오고, 고르고 쉽게 풀어 주고 '금리·물가·환율 중 무엇과 연결되는지'는 Claude가 합니다.

  📰 읽기     econ_news(topic)    → 한 주제의 최신 기사
              econ_briefing()     → 세 주제(금리, 물가·성장, 환율·증시)를 한 번에
  📝 기록     save_reading        → 읽은 기사 중 남길 것을 공부노트.md에 저장
              list_readings       → 최근 공부 기록 보기
  ☀️ 양식     daily_econ_reading  → 매일 아침 읽기 루틴 (Prompt)

실행:      uv run server.py
테스트:    uv run test_client.py
"""
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

mcp = MCPServer("econ-news")

HERE = Path(__file__).parent
NOTEBOOK = HERE / "공부노트.md"

# 주제 이름 → 구글 뉴스 검색어. OR로 비슷한 말을 묶으면 놓치는 기사가 줄어듭니다.
# 관심 주제가 생기면 한 줄만 추가하세요. 예: "부동산": "집값 OR 전세 OR 주택담보대출"
TOPICS = {
    "금리": "기준금리 OR 한국은행 OR 금통위 OR 연준 금리",
    "물가·성장": "소비자물가 OR 경제성장률 OR GDP OR 경기 전망",
    "환율·증시": "원달러 환율 OR 코스피 마감 OR 외국인 순매도",
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _google_news_url(query: str, days: int) -> str:
    """when:Nd 를 붙이면 최근 N일 기사만 찾습니다."""
    return f"https://news.google.com/rss/search?q={quote(f'{query} when:{days}d')}&hl=ko&gl=KR&ceid=KR:ko"


def _parse_feed(xml_bytes: bytes) -> list[dict]:
    """RSS를 기사 목록으로 바꿉니다. (인터넷 없이도 테스트할 수 있게 읽기와 분리)"""
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        title = item.findtext("title", "").strip()
        source = item.findtext("source", "").strip()
        if source and title.endswith(f" - {source}"):      # 구글 뉴스 제목 끝의 " - 언론사" 정리
            title = title[: -len(source) - 3]
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (TypeError, ValueError):
            published = None
        items.append({"title": title, "source": source, "date": published,
                      "link": item.findtext("link", "").strip()})
    items.sort(key=lambda x: x["date"].timestamp() if x["date"] else 0, reverse=True)
    return items


def _fetch(query: str, days: int) -> list[dict]:
    req = Request(_google_news_url(query, days), headers={"User-Agent": "Mozilla/5.0 (econ-news)"})
    with urlopen(req, timeout=10) as res:
        return _parse_feed(res.read())


def _format(item: dict) -> str:
    when = item["date"].strftime("%m-%d") if item["date"] else "날짜 없음"
    src = f" · {item['source']}" if item["source"] else ""
    return f"- {item['title']} ({when}{src})\n  {item['link']}"


@mcp.tool()
def econ_news(topic: str, count: int = 5, days: int = 7) -> str:
    """경제 관련 최신 뉴스 제목, 날짜, 언론사, 링크를 가져옵니다. 금리·물가·환율·증시 소식을 물으면 사용하세요.
    topic: 금리, 물가·성장, 환율·증시 중 하나. 그 밖의 단어(예: 반도체 수출, 전세)는 그대로 검색합니다.
    count: 기사 개수(기본 5). days: 최근 며칠 기사만 볼지(기본 7)."""
    query = TOPICS.get(topic, topic)
    try:
        items = _fetch(query, days)[:count]
    except (OSError, ET.ParseError) as e:
        log(f"news error: {e}")
        return f"'{topic}' 뉴스를 가져오지 못했어요 ({e}). 인터넷 연결을 확인해 주세요."
    if not items:
        return f"최근 {days}일 동안 '{topic}' 관련 기사를 찾지 못했어요. days를 늘려 보세요."
    return f"[{topic}] 최근 {days}일 기사 {len(items)}개\n" + "\n".join(_format(i) for i in items)


@mcp.tool()
def econ_briefing(count: int = 3, days: int = 1) -> str:
    """오늘의 경제 브리핑: 금리, 물가·성장, 환율·증시 세 주제의 최신 기사를 한 번에 가져옵니다.
    '오늘 경제 뉴스', '아침 브리핑'을 물으면 사용하세요. 주제끼리 겹치는 기사는 한 번만 보여 줍니다.
    count: 주제별 기사 개수(기본 3). days: 최근 며칠(기본 1, 기사가 적으면 늘리세요)."""
    seen, blocks = set(), []
    for topic, query in TOPICS.items():
        try:
            items = [i for i in _fetch(query, days) if i["title"] not in seen][:count]
        except (OSError, ET.ParseError) as e:     # 한 주제가 실패해도 나머지는 계속
            log(f"briefing error ({topic}): {e}")
            blocks.append(f"## {topic}\n(가져오지 못했어요: {e})")
            continue
        seen.update(i["title"] for i in items)
        body = "\n".join(_format(i) for i in items) or "(새 기사 없음)"
        blocks.append(f"## {topic}\n{body}")
    return f"# {date.today()} 경제 브리핑 (최근 {days}일)\n\n" + "\n\n".join(blocks)


@mcp.tool()
def save_reading(title: str, link: str, memo: str, topic: str = "") -> str:
    """읽은 기사 중 기억할 만한 것을 공부노트.md에 저장합니다.
    memo에는 기사 요약이 아니라 '내 말로 이해한 것, 또는 나에게(내 돈에) 어떤 의미인지' 한두 줄을 적으세요."""
    today = date.today().isoformat()
    text = NOTEBOOK.read_text(encoding="utf-8") if NOTEBOOK.exists() else "# 경제 공부노트\n"
    heading = f"\n## {today}\n"
    if heading not in text:
        text += heading
    tag = f"[{topic}] " if topic else ""
    text += f"- {tag}[{title}]({link})\n  - {memo}\n"
    NOTEBOOK.write_text(text, encoding="utf-8")
    log(f"reading saved: {title}")
    return f"공부노트에 저장했어요: {title}"


@mcp.tool()
def list_readings(days: int = 7) -> str:
    """최근 N일(기본 7) 동안 공부노트에 저장한 기록을 보여 줍니다. 주간 복습에 사용하세요."""
    if not NOTEBOOK.exists():
        return "아직 저장한 기록이 없어요."
    since = date.today() - timedelta(days=days - 1)
    out, keep = [], False
    for line in NOTEBOOK.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            try:
                keep = date.fromisoformat(line[3:].strip()) >= since
            except ValueError:
                keep = False
        if keep and line.strip():
            out.append(line)
    return "\n".join(out) if out else f"최근 {days}일 동안 저장한 기록이 없어요."


@mcp.prompt()
def daily_econ_reading() -> str:
    """매일 아침 10분 경제 뉴스 읽기 루틴."""
    return """오늘의 경제 뉴스 읽기를 도와주세요. 저는 경제 완전 초보입니다.

1. econ_briefing으로 오늘 기사를 가져오세요. 기사가 거의 없으면 days=3으로 다시 가져오세요.
2. 주제(금리, 물가·성장, 환율·증시)마다 초보가 꼭 알아야 할 기사 1개씩 고르세요.
3. 고른 기사마다:
   - 무슨 일인지 중학생도 알 수 있는 말로 2줄
   - 금리·물가·환율·성장 중 무엇과 연결되는지 1줄
   - 기사에 나온 어려운 용어 1개와 한 줄 뜻
   - "그래서 내 돈(예금·대출·물가)에는?" 생각해 볼 질문 1개
4. 마지막에 3개 중 하나를 골라 save_reading으로 저장할지 물어보세요.
기사 제목만으로 알 수 없는 내용은 추측하지 말고 "원문 확인 필요"라고 적어 주세요."""


if __name__ == "__main__":
    mcp.run()
