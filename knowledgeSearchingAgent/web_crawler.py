import asyncio
from crawl4ai import AsyncWebCrawler

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://arxiv.org/search/cs?query=Education+AI&searchtype=all&abstracts=show&order=-announced_date_first&size=50",
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())