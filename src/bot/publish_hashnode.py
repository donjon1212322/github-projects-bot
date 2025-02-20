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
            json.dump(published_posts, f, indent=4)

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

    mutation = """
    mutation CreateDraft($input: CreateDraftInput!) {
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
            data = response_data.get("data")
            if not data:
                logging.error(f"No 'data' field found in response.  Full response: {json.dumps(response_data, indent=4)}")
                if 'errors' in response_data:
                    logging.error(f"Errors: {response_data['errors']}")
                return

            create_draft = data.get("createDraft")
            if create_draft:
                draft_info = create_draft.get("draft")
                if draft_info:
                    draft_id = draft_info.get('id')
                    logging.info(f"Draft successfully created on Hashnode! Draft ID: {draft_id}")

                    if publish_directly:  # Now publish the draft
                        draft_id = draft_info.get('id')
                        publish_mutation = """
                        mutation PublishDraft($input: PublishDraftInput!) {
                            publishDraft(input: $input) {
                                post {
                                    id
                                    slug
                                    url
                                }
                            }
                        }
                        """
                        publish_variables = {
                            "input": {
                                "draftId": draft_id
                            }
                        }
                        publish_payload = {
                            "query": publish_mutation,
                            "variables": publish_variables
                        }

                        logging.info("Publish Request Payload:")
                        logging.info(json.dumps(publish_payload, indent=4))

                        publish_response = requests.post(api_endpoint, headers=headers, json=publish_payload, timeout=30)
                        publish_response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                        try:
                            publish_response_data = publish_response.json()
                            logging.info("Publish Response data:")
                            logging.info(json.dumps(publish_response_data, indent=4))

                            publish_data = publish_response_data.get("data")

                            if publish_data:
                                publish_draft_result = publish_data.get("publishDraft")
                                if publish_draft_result:
                                    post_info = publish_draft_result.get("post")
                                    if post_info:
                                        logging.info("Post successfully published on Hashnode!")
                                        post_id = post_info.get('id')
                                        logging.info(f"Post ID: {post_id}")
                                        save_published_post(project_id)
                                    else:
                                        logging.error("Post publication failed; no post information returned.")
                                else:
                                   logging.error("Publish Draft failed, no post information found")

                            else:
                                logging.error("No data found from publish response")

                        except json.JSONDecodeError:
                            logging.error("Failed to decode JSON publish response")
                            logging.error(f"Raw publish response: {publish_response.text}")
                            return

                else:
                    logging.error("Draft creation failed; no draft information returned.")
            else:
                draft_info = create_draft.get("draft")
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

    project_id = article_data.get("project_id")
    logging.info(f"Project ID: {project_id}")

    # Set publish_directly to True to publish directly to production
    publish_to_hashnode(article_data, publish_directly=True)

if __name__ == "__main__":
    main()