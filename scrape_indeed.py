from bs4 import BeautifulSoup

def scrape_indeed():
    url = "https://www.indeed.com/jobs?q=QA+Automation&l=Remote"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    jobs = []
    for card in soup.select(".job_seen_beacon"):
        title = card.select_one("h2").text.strip()
        link = "https://www.indeed.com" + card.select_one("a")["href"]

        jobs.append({
            "company": "Indeed Listing",
            "title": title,
            "link": link,
            "location": "Remote",
            "description": ""
        })
    return jobs
