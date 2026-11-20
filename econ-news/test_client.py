"""서버가 잘 동작하는지 확인하는 테스트 클라이언트: uv run test_client.py
(뉴스 도구는 인터넷이 필요합니다. 연결이 안 되면 에러 대신 이유 문장이 나오면 정상)"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def text(r):
    if r.structured_content is not None:
        return r.structured_content.get("result", r.structured_content)
    return " ".join(c.text for c in r.content)


async def main():
    params = StdioServerParameters(command=sys.executable, args=["server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            call = lambda name, args={}: s.call_tool(name, args)
            print("도구 목록:", [t.name for t in (await s.list_tools()).tools])
            print("\n[금리]\n" + text(await call("econ_news", {"topic": "금리", "count": 3})))
            print("\n[자유 검색: 반도체 수출]\n" + text(await call("econ_news", {"topic": "반도체 수출", "count": 2})))
            print("\n[브리핑]\n" + text(await call("econ_briefing", {"count": 2, "days": 3})))
            print("\n[저장]\n" + text(await call("save_reading", {
                "title": "테스트 기사", "link": "https://example.com",
                "memo": "금리가 오르면 내 예금 이자도 오르는지 확인", "topic": "금리"})))
            print("\n[기록 보기]\n" + text(await call("list_readings")))
            p = await s.get_prompt("daily_econ_reading", {})
            print("\n[prompt]\n" + p.messages[0].content.text.splitlines()[0])


asyncio.run(main())
