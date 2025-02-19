import json
import os
import requests
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

HASHNODE_API_KEY = os.getenv("HASHNODE_API_KEY")
HASHNODE_PUBLICATION_ID = os.getenv("HASHNODE_PUBLICATION_ID")

def load_published_posts():
    try:
        with open("data/published_posts_hashnode.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_published_post(project_id):
    published_posts = load_published_posts()
    if project_id not in published_posts:
        published_posts.append(project_id)
        with open("data/published_posts_hashnode.json", "w") as f:
            json.dump(published_posts, f)

def publish_to_hashnode(article_data, publish_directly=False):
    project_id = article_data.get("project_id")
    if not project_id:
        logging.error("No project ID found in the article data.")
        return

    published_posts = load_published_posts()
    if project_id in published_posts:
        logging.info(f"Article with project ID {project_id} has already been published. Skipping.")
        return

    api_endpoint = "https://gql.hashnode.com"
    headers = {
        "Content-Type": "application/json",
        "Authorization": HASHNODE_API_KEY,
    }

    # Choose mutation based on publish_directly flag
    if publish_directly:
        mutation = """
        mutation publishStory($input: CreateStoryInput!) {
            createPublicationStory(input: $input) {
                post {
                    id
                    slug
                    url
                }
            }
        }
        """
    else:
        mutation = """
        mutation createDraft($input: CreateDraftInput!) {
            createDraft(input: $input) {
                draft {
                    id
                    slug
                }
            }
        }
        """

    variables = {
        "input": {
            "title": article_data["title"],
            "contentMarkdown": article_data["contentMarkdown"],
            "tags": article_data["tags"],
            "publicationId": HASHNODE_PUBLICATION_ID,
            "subtitle": article_data.get("subtitle", ""),
            "slug": article_data.get("slug", ""),
            "coverImageOptions": {
                "url": article_data.get("coverImage", "")
            } if article_data.get("coverImage") else None,
        }
    }

    payload = {
        "query": mutation,
        "variables": variables
    }

    logging.info("Request Payload:")
    logging.info(json.dumps(payload, indent=4))

    try:
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=30)
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response headers: {response.headers}")
        response.raise_for_status()

        try:
            response_data = response.json()
            logging.info("Response data:")
            logging.info(json.dumps(response_data, indent=4))
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON response")
            logging.error(f"Raw response: {response.text}")
            return

        if isinstance(response_data, dict):
            if publish_directly:
                post_info = response_data.get("data", {}).get("createPublicationStory", {}).get("post")
                if post_info:
                    logging.info("Post successfully published on Hashnode!")
                    post_id = post_info.get('id')
                    logging.info(f"Post ID: {post_id}")
                    save_published_post(project_id)
                else:
                    logging.error("Post publication failed; no post information returned.")
            else:
                draft_info = response_data.get("data", {}).get("createDraft", {}).get("draft")
                if draft_info:
                    logging.info("Draft successfully created on Hashnode!")
                    draft_id = draft_info.get('id')
                    logging.info(f"Draft ID: {draft_id}")
                    save_published_post(project_id)
                else:
                    logging.error("Draft creation failed; no draft information returned.")
        else:
            error_message = response_data.get("errors", [{}])[0].get("message", "Unknown error")
            logging.error(f"Failed to create draft. Error: {error_message}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error occurred: {e}")
        if hasattr(e, 'response'):
            logging.error(f"Response content: {e.response.text}")

def main():
    try:
        with open("data/hashnode_post.json", "r", encoding="utf-8") as f:
            article_data = json.load(f)
    except FileNotFoundError:
        print("Error: data/hashnode_post.json not found. Please run formated_hashnode.py first.")
        return

    if not HASHNODE_API_KEY:
        print("Error: HASHNODE_API_KEY not found in environment variables. Set it before running this script.")
        return

    if not HASHNODE_PUBLICATION_ID:
        print("Error: HASHNODE_PUBLICATION_ID not found in environment variables. Set it before running this script.")
        return

    # Set publish_directly to True to publish directly to production
    publish_to_hashnode(article_data, publish_directly=True)

if __name__ == "__main__":
    main()
