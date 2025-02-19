import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Загрузка переменных окружения
load_dotenv()

# Получение токенов из переменных окружения
GH_API_TOKEN = os.getenv("GH_API_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка модели Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def fetch_github_graphql(session, query):
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    async with session.post(url, json={"query": query}, headers=headers) as response:
        response.raise_for_status()
        return await response.json()

async def get_best_repository():
    with open("data/projects.json", "r", encoding="utf-8") as f:
        projects = json.load(f)
    # Найти репозиторий с наивысшим quality_score
    best_repo = max(projects, key=lambda x: x['quality_score'])
    return best_repo

async def get_readme_content(session, owner, repo):
    query = f"""
    query {{
      repository(owner: "{owner}", name: "{repo}") {{
        object(expression: "main:README.md") {{
          ... on Blob {{
            text
          }}
        }}
      }}
    }}
    """
    data = await fetch_github_graphql(session, query)
    if data and 'data' in data and 'repository' in data['data'] and 'object' in data['data']['repository']:
        return data['data']['repository']['object']['text']
    else:
        print("Failed to fetch README content or unexpected data structure.")
        print(f"Response data: {data}")
        return None

async def generate_article_from_readme(readme_content):
    prompt = (
        "You are a skilled tech blogger writing a short, engaging article for developers about a GitHub repository.\n"
        "Your goal is to capture the reader's attention and explain the project in a way that is easy to understand.\n"
        "Write in simple terms, avoiding jargon, and focus on what makes the project interesting and useful.\n"
        "The article must be at least 1000 characters long.\n"
        "Include a catchy title and highlight the project's key benefits for developers.\n"
        "Provide a list of 3-5 'Key Takeaways' that summarize the project's most important aspects.\n"
        "Tags:** A set of 3-5 relevant keywords that will help people find the article (focus on core technologies and use cases)"
        "Use a conversational and enthusiastic tone.\n\n"
        f"Here is the content of the README.md file:\n{readme_content[:4000]}\n\n"
        "Provide the response in JSON format according to the specified schema:"
    )

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "An engaging and attention-grabbing title for the article"
                    },
                    "article": {
                        "type": "string",
                        "description": "The *main content* of the article, written in simple terms, at least 500 characters long. Explain the project's purpose, how it works, and why developers should care about it. *DO NOT* include a title, introduction, key takeaways, statistics, or any other metadata."
                    },
                    "key_takeaways": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "A list of 3-5 key takeaways that summarize the project's most important aspects and benefits for developers."
                    },
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "A list of 3-5 relevant tags for the article."
                    }
                },
                "required": ["title", "article", "key_takeaways", "tags"]
            }
        )
    )

    try:
        response_data = json.loads(response.text)
        return response_data
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        return None

async def main():
    async with aiohttp.ClientSession() as session:
        best_repo = await get_best_repository()
        repo_url = best_repo['url']
        owner, repo = repo_url.split('/')[-2:]
        readme_content = await get_readme_content(session, owner, repo)
        if readme_content:
            article_data = await generate_article_from_readme(readme_content)
            if article_data:
                # Incorporate data from best_repo into article_data
                article_data["title"] = article_data.get("title", best_repo.get("name", "No Title")) # Use Gemini title if present, else repo name
                article_data["stars"] = best_repo.get("stars", 0)
                article_data["forks"] = best_repo.get("forks", 0)
                article_data["open_issues"] = best_repo.get("open_issues", 0)
                article_data["languages"] = best_repo.get("language", "Not specified")  # Add languages
                article_data["readme_summary"] = best_repo.get("readme_summary", "") # Add readme_summary
                # Add other fields from best_repo that you want to save
                article_data["project_id"] = best_repo.get("id")
                article_data["url"] = best_repo.get("url")
                article_data["description"] = best_repo.get("description")

                # Save to data directory in JSON format
                output_path = os.path.join("data", "article_output.json") # Corrected path
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(article_data, f, indent=4, ensure_ascii=False) # This should create a valid JSON
                print(f"Article saved to {output_path}") # Updated output message
            else:
                print("Failed to generate article.")
        else:
            print("Could not generate article due to missing README content.")

if __name__ == "__main__":
    asyncio.run(main())