import asyncio
import aiohttp
import json
from datetime import datetime, timedelta, timezone
from github import Github
import os
from dotenv import load_dotenv
import re
import logging
import urllib.parse
from telethon import TelegramClient, events, sync
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import PeerChannel
import requests
import random
import google.generativeai as genai

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Замените на свой токен GitHub
GH_API_TOKEN = os.getenv("GH_API_TOKEN")
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING")
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME")
TELEGRAM_CHANNEL_USERNAME_2 = os.getenv("TELEGRAM_CHANNEL_USERNAME_2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini model
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-preview-09-2025")

async def fetch_telegram_posts(api_id, api_hash, channel_username, session_string):
    try:
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        await client.connect()
        if not client.is_connected():
            logging.error("Failed to connect to Telegram.")
            return []

        channel = await client.get_entity(channel_username)
        if not channel:
            logging.error(f"Chat not found for username: {channel_username}")
            await client.disconnect()
            return []

        messages = []
        last_day = datetime.now(timezone.utc) - timedelta(days=1)
        
        async for message in client.iter_messages(channel, limit=None):
            if message.date and message.date > last_day and message.text:
                messages.append(message.text)
                logging.info(f"Получено сообщение от {message.date}")
            elif message.date and message.date <= last_day:
                logging.info(f"Достигнут предел в 24 часов на сообщении от {message.date}")
                break # Если сообщение старше двух суток, то выходим из цикла
            if len(messages) > 4:
                logging.info("Достигнут лимит в 10 сообщений, прекращаем получение")
                break # Ограничение на количество сообщений
        
        await client.disconnect()
        return messages
    except Exception as e:
        logging.error(f"Error fetching Telegram posts with Telethon: {e}")
        return []

async def fetch_github_data(session, query):
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=1"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    logging.info(f"Fetching data from: {url}")
    async with session.get(url, headers=headers) as response:
        try:
            response.raise_for_status()
            return await response.json()
        except aiohttp.ClientResponseError as e:
            logging.error(f"Error fetching data from {url}: {e}")
            logging.error(f"Response text: {await response.text()}")
            raise

async def fetch_github_graphql(session, query):
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    logging.info(f"Fetching data from: {url}")
    async with session.post(url, json={"query": query}, headers=headers) as response:
        try:
            response.raise_for_status()
            return await response.json()
        except aiohttp.ClientResponseError as e:
            logging.error(f"Error fetching data from {url}: {e}")
            logging.error(f"Response text: {await response.text()}")
            raise

def analyze_project(repo):
    score = 0
    if repo.description and len(repo.description) > 100:
        score += 0.15
    if repo.get_readme():
        score += 0.15
    if repo.get_issues(state='open').totalCount > 0:
        score += 0.1
    if repo.get_pulls(state='open').totalCount > 0:
        score += 0.1
    if repo.get_contributors().totalCount > 1:
        score += 0.2
    
    last_commit_date = repo.get_commits().get_page(0)[0].commit.author.date if repo.get_commits().totalCount > 0 else None
    if last_commit_date:
        days_since_last_commit = (datetime.now(timezone.utc) - last_commit_date).days
        if days_since_last_commit < 30:
            score += 0.3
        elif days_since_last_commit < 90:
            score += 0.15
    
    try:
        if repo.get_contents("tests"):
            score += 0.1
    except:
        pass
    
    try:
        if repo.get_contents(".github/workflows"):
            score += 0.1
    except:
        pass
    
    return score

async def extract_media_urls(repo):
    try:
        graphql_query = f"""
            query {{
                repository(owner: "{repo.owner.login}", name: "{repo.name}") {{
                    openGraphImageUrl
                    homepageUrl
                }}
            }}
        """
        async with aiohttp.ClientSession() as session:
            graphql_data = await fetch_github_graphql(session, graphql_query)
            media_url = graphql_data.get("data", {}).get("repository", {}).get("openGraphImageUrl")
            homepage_url = graphql_data.get("data", {}).get("repository", {}).get("homepageUrl")
            
            if media_url:
                logging.info(f"Found media URL from GraphQL: {media_url}")
                return [media_url], homepage_url
            else:
                logging.info(f"No media URL found from GraphQL for repo: {repo.name}")
                return [], homepage_url
    except Exception as e:
        logging.error(f"Error extracting media URLs: {e}")
        return [], None

async def generate_summary(repo, readme):
    try:
        prompt = (
            "Analyze the following GitHub repository README and provide a structured response "
            "focusing only on relevant technical information.\n\n"
            f"Repository: {repo.name}\n"
            f"Description: {repo.description}\n"
            f"Language: {repo.language}\n"
            f"Topics: {', '.join(repo.get_topics()) if repo.get_topics() else 'None'}\n\n"
            f"README content:\n{readme[:4000]}\n\n"
            
            "CRITICAL INSTRUCTION FOR LEONARDO.AI IMAGE PROMPT CREATION:\n\n"
            
            "You are tasked with creating a prompt for Leonardo.AI that will generate a CONCEPTUAL ILLUSTRATION "
            "that clearly shows what this repository does in a SINGLE, CLEAR VISUAL METAPHOR.\n\n"
            
            "DO NOT create a technical diagram, code screen, or abstract tech visualization. "
            "Instead, create a prompt for a CONCEPTUAL ILLUSTRATION that shows what the repository does "
            "through a clear, intuitive visual metaphor that anyone could understand.\n\n"
            
            "Follow these steps:\n\n"
            
            "1. IDENTIFY THE CORE PURPOSE: What is the single most important thing this repository does? "
            "Example: 'This repository helps developers test their APIs' or 'This repository converts PDFs to text'\n\n"
            
            "2. CREATE A VISUAL METAPHOR: Think of a clear, intuitive visual metaphor that represents this function. "
            "Example: For an API testing tool, the metaphor could be 'a scientist in a lab testing different chemicals' "
            "or for a PDF converter, 'a translator reading a book and writing down notes'\n\n"
            
            "3. DESCRIBE A SINGLE SCENE: Describe a single, clear scene that shows this metaphor in action. Focus on:\n"
            "   - A main character or object performing the core function\n"
            "   - Clear visual indicators of the input and output\n"
            "   - Simple, intuitive visual elements that anyone can understand\n"
            "   - A clean, focused composition with minimal distractions\n\n"
            
            "4. ADD SUBTLE TECH ELEMENTS: Add subtle tech elements that connect the metaphor to software, such as:\n"
            "   - Small UI elements or screens showing the actual function\n"
            "   - Digital particles or glowing elements\n"
            "   - Small code snippets or data visualizations as secondary elements\n"
            "   - The repository name subtly incorporated into the scene\n\n"
            
            "5. SPECIFY ARTISTIC STYLE: Request a specific artistic style that enhances understanding, such as:\n"
            "   - 3D isometric illustration\n"
            "   - Flat design with clear iconography\n"
            "   - Digital painting with clear outlines\n"
            "   - Technical illustration with labeled parts\n\n"
            
            "EXAMPLE PROMPT STRUCTURE:\n"
            "\"A [SPECIFIC CHARACTER/OBJECT] [PERFORMING THE CORE FUNCTION] with [INPUT] and transforming it into [OUTPUT]. "
            "The scene shows [VISUAL METAPHOR DETAILS] in a [SETTING] with [LIGHTING/MOOD]. Small digital elements like "
            "[TECH ELEMENT 1] and [TECH ELEMENT 2] subtly connect the metaphor to software. The composition is [COMPOSITION DETAILS] "
            "with [COLOR SCHEME]. The image should be in [ARTISTIC STYLE] style with [QUALITY DETAILS].\"\n\n"
            
            "EXAMPLES OF GOOD PROMPTS:\n"
            "- For a data visualization library: \"A wizard standing before a blank canvas, transforming scrolls of numbers into "
            "vibrant, floating charts and graphs. The wizard's wand emits particles of data that flow onto the canvas, creating "
            "beautiful visualizations. Small screens around the scene show actual code and the resulting charts. The scene is set "
            "in a modern study with warm lighting. The image should be in 3D isometric illustration style with rich details and vibrant colors.\"\n\n"
            
            "- For a security scanning tool: \"A vigilant guardian with a glowing shield inspecting packages before they enter a "
            "futuristic city gate. The guardian uses a special lens to see inside each package, revealing hidden threats that glow red. "
            "Successfully scanned packages emit a green aura as they pass through. Small monitors around the gate show scanning logs "
            "and security metrics. The scene has a blue and purple color scheme with dramatic lighting. The image should be in digital "
            "painting style with clean lines and clear details.\"\n\n"
            
            "The Leonardo.AI prompt should be 100-150 words, focused on creating a SINGLE, CLEAR VISUAL METAPHOR "
            "that immediately communicates what the repository does to anyone who sees it."
        )
        
        response = model.generate_content(
            prompt,
            generation_config = genai.GenerationConfig(
                temperature=0.3,
                top_p=0.8,
                top_k=40,
                response_mime_type="application/json",
                response_schema = {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "A 2-3 sentence summary of the repository's main features and use cases"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of main features mentioned in README"
                        },
                        "primary_use_case": {
                            "type": "string",
                            "description": "The primary intended use case of the repository"
                        },
                        "cover_image_prompt": {
                            "type": "string",
                            "description": "A 100-150 word prompt for Leonardo.AI that will generate a conceptual illustration showing what the repository does through a clear visual metaphor"
                        }
                    },
                    "required": ["summary", "key_features", "primary_use_case", "cover_image_prompt"]
                }
            )
        )
        
        logging.info(f"Gemini raw response: {response.text}")
        
        try:
            response_data = json.loads(response.text)
            return response_data
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response: {e}")
            return None
    except Exception as e:
        logging.warning(f"Couldn't process README: {str(e)}")
        return None




async def main():
    telegram_posts = await fetch_telegram_posts(TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL_USERNAME, TELEGRAM_SESSION_STRING)
    telegram_posts_2 = await fetch_telegram_posts(TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL_USERNAME_2, TELEGRAM_SESSION_STRING)
    
    github_links = []
    for post in telegram_posts:
        links = re.findall(r'https://github\.com/[\w\-\_]+/[\w\-\_]+', post)
        github_links.extend(links)
        logging.info(f"Found links in post from {TELEGRAM_CHANNEL_USERNAME}: {links}")
    
    for post in telegram_posts_2:
        links = re.findall(r'https://github\.com/[\w\-\_]+/[\w\-\_]+', post)
        github_links.extend(links)
        logging.info(f"Found links in post from {TELEGRAM_CHANNEL_USERNAME_2}: {links}")
    
    g = Github(GH_API_TOKEN)
    async with aiohttp.ClientSession() as session:
        projects = []
        # Load published post IDs from file
        published_posts = []
        try:
            with open("data/published_posts.json", "r") as f:
                published_posts = json.load(f)
            logging.info(f"Loaded published post IDs: {published_posts}")
        except FileNotFoundError:
            logging.warning("data/published_posts.json not found.  Starting with an empty list.")
        except json.JSONDecodeError:
            logging.error("Error decoding data/published_posts.json. Starting with an empty list.")
        
        for link in github_links:
            try:
                repo_name = link.replace("https://github.com/", "")
                repo = g.get_repo(repo_name)
                
                # Check if the post is already published
                if repo.id in published_posts:
                    logging.info(f"Skipping already published repository: {repo_name} (ID: {repo.id})")
                    continue
                
                query = f"repo:{repo_name} has:readme"
                encoded_query = urllib.parse.quote(query)
                data = await fetch_github_data(session, encoded_query)
                
                if data.get("total_count", 0) > 0:
                    item = data.get("items", [])[0]
                    if repo.language:
                        quality_score = analyze_project(repo)
                        
                        graphql_query = f"""
                            query {{
                                repository(owner: "{repo.owner.login}", name: "{repo.name}") {{
                                    collaborators {{
                                        totalCount
                                    }}
                                    
                                    defaultBranchRef {{
                                        target {{
                                            ... on Commit {{
                                                history(first: 1) {{
                                                    edges {{
                                                        node {{
                                                            committedDate
                                                        }}
                                                    }}
                                                }}
                                            }}
                                        }}
                                    }}
                                    openIssues: issues(states:OPEN) {{
                                        totalCount
                                    }}
                                }}
                            }}
                            """
                        
                        graphql_data = await fetch_github_graphql(session, graphql_query)
                        contributors_count = graphql_data.get("data", {}).get("repository", {}).get("collaborators", {}).get("totalCount", 0) if graphql_data and graphql_data.get("data", {}).get("repository", {}).get("collaborators") else 0
                        
                        last_commit_date = None
                        
                        if graphql_data and graphql_data.get("data", {}).get("repository", {}).get("defaultBranchRef", {}):
                            edges = graphql_data.get("data", {}).get("repository", {}).get("defaultBranchRef", {}).get("target", {}).get("history", {}).get("edges", [])
                            if edges:
                                last_commit_date = edges[0].get("node", {}).get("committedDate")
                        
                        open_issues_count = graphql_data.get("data", {}).get("repository", {}).get("openIssues", {}).get("totalCount", 0)
                        media_urls, homepage_url = await extract_media_urls(repo)
                        
                        readme = repo.get_readme().decoded_content.decode()
                        summary_data = await generate_summary(repo, readme)
                        
                        projects.append({
                            "id": item["id"],
                            "name": item["name"],
                            "description": item["description"],
                            "url": item["html_url"],
                            "language": item["language"],
                            "stars": item["stargazers_count"],
                            "forks": item["forks_count"],
                            "created_at": str(item["created_at"]),
                            "updated_at": str(item["updated_at"]),
                            "topics": item.get("topics", []),
                            "quality_score": quality_score,
                            "contributors_count": contributors_count,
                            "last_commit_date": last_commit_date,
                            "media_urls": media_urls,
                            "homepage": homepage_url,
                            "readme_summary": summary_data.get("summary") if summary_data else None,
                            "key_features": summary_data.get("key_features") if summary_data else [],
                            "primary_use_case": summary_data.get("primary_use_case") if summary_data else None,
                            "open_issues": open_issues_count,
                            "cover_image_prompt": summary_data.get("cover_image_prompt") if summary_data else None
                        })
            except Exception as e:
                logging.error(f"Error processing link {link}: {e}")
        
        # Сохраняем данные в файл
        with open("data/projects.json", "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=4, ensure_ascii=False, default=str)
        
        print("Data collected and saved to data/projects.json")

if __name__ == "__main__":
    asyncio.run(main())

