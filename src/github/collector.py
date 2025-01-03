import aiohttp
import asyncio
import json
import os
from datetime import datetime, date, timedelta
from github import Github
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def fetch_github_projects(g, query):
    search_results = g.search_repositories(query, sort="stars", order="desc")
    return search_results


async def analyze_project(repo):
    project = {
        "id": repo.id,
        "name": repo.name,
        "description": repo.description,
        "url": repo.html_url,
        "language": repo.language,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "created_at": repo.created_at.isoformat(),
        "updated_at": repo.updated_at.isoformat(),
        "topics": repo.get_topics(),
    }
    return project


async def main():
    logging.info("Starting project collection")
    try:
        # GitHub API token (using os.environ instead of github actions secrets)
        g = Github(os.environ.get("GITHUB_TOKEN"))
        today = date.today()
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        query = f"stars:>1000 pushed:>{yesterday_str}"

        logging.info(f"Searching with query: {query}")
        search_results = await fetch_github_projects(g, query)

        projects = []
        if search_results:
            counter = 0
            for repo in search_results:
                if counter >= 10:
                    break
                project = await analyze_project(repo)
                projects.append(project)
                counter += 1
            logging.info(f"Found {counter} projects")
        else:
           logging.info("No projects found")

        with open("data/projects.json", "w") as f:
            json.dump(projects, f, indent=4)
    except Exception as e:
        logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())