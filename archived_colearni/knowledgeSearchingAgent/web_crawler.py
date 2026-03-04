import asyncio
import os
from crawl4ai import AsyncWebCrawler

async def main():
    url = "https://arxiv.org/search/cs?query=Education+AI&searchtype=all&abstracts=show&order=-announced_date_first&size=50&start=50"
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
        )
        
        # Store this in a md file generate the file name from the source
        source = url.split("/")[2].replace(".", "_")
        print(source)
        # Check if file exists and append number if it does
        base_filename = f"{source}.md"
        filename = base_filename
        counter = 1
        while os.path.exists(filename):
            filename = f"{source}_{counter}.md"
            counter += 1
            
        with open(filename, "w", encoding="utf-8") as f:
            f.write(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())