import json
import os
import time
import asyncio
import aiohttp
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Constants ---
API_ENDPOINT = 'https://api.leonardo.ai/v1/graphql'
IMAGE_SAVE_DIR = "images"  # Directory to save images
MAX_WAIT_TIME = 300  # Maximum wait time for generation completion (in seconds)
POLL_INTERVAL = 10  # Interval between requests (in seconds)
SESSION_URL = "https://app.leonardo.ai/api/auth/session"
PROJECTS_JSON_PATH = "data/projects.json"  # Path to projects.json

# --- Async Functions ---
async def get_access_token():
    headers = {
        'accept': '*/*',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'dnt': '1',
        'priority': 'u=1, i',
        'referer': 'https://app.leonardo.ai/image-generation',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    }
    
    session_token_0 = os.getenv('SESSION_TOKEN_0')
    session_token_1 = os.getenv('SESSION_TOKEN_1')
    
    if not session_token_0 or not session_token_1:
        print("Error: SESSION_TOKEN_0 or SESSION_TOKEN_1 not found in .env file.")
        return None
        
    cookies = {
        '__Secure-next-auth.session-token.0': session_token_0,
        '__Secure-next-auth.session-token.1': session_token_1,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SESSION_URL, headers=headers, cookies=cookies) as response:
                response.raise_for_status()
                session_data = await response.json()
                api_key = session_data.get("accessToken")
                
                if not api_key:
                    print("Error: Access token not found in session data.")
                    return None
                    
                return api_key
    except aiohttp.ClientError as e:
        print(f"Error getting session info: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error parsing JSON: {e}")
        return None

async def create_generation_job(api_key, prompt):
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'dnt': '1',
        'origin': 'https://app.leonardo.ai',
        'priority': 'u=1, i',
        'referer': 'https://app.leonardo.ai/',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'authorization': f'Bearer {api_key}'
    }
    
    query = """
    mutation CreateSDGenerationJob($arg1: SDGenerationInput!) {
      sdGenerationJob(arg1: $arg1) {
        generationId
        __typename
      }
    }
    """
    
    data = {
        "operationName": "CreateSDGenerationJob",
        "variables": {
            "arg1": {
                "prompt": prompt,
                "negative_prompt": "",
                "nsfw": True,
                "num_images": 1,
                "width": 1184,
                "height": 672,
                "image_size": 1,
                "num_inference_steps": 10,
                "contrast": 3.5,
                "guidance_scale": 7,
                "sd_version": "PHOENIX",
                "modelId": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3",
                "presetStyle": "LEONARDO",
                "scheduler": "LEONARDO",
                "public": True,
                "tiling": False,
                "leonardoMagic": False,
                "poseToImage": False,
                "poseToImageType": "POSE",
                "presetId": 430,
                "weighting": 0.75,
                "highContrast": False,
                "elements": [],
                "userElements": [],
                "controlnets": [],
                "photoReal": False,
                "transparency": "disabled",
                "styleUUID": "111dc692-d470-4eec-b791-3475abac4c46",
                "enhancePrompt": True,
                "collectionIds": [],
                "ultra": False
            }
        },
        "query": query
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_ENDPOINT, headers=headers, json=data) as response:
                response.raise_for_status()
                response_data = await response.json()
                
                # Log full response for debugging
                print("API Response:", response_data)
                
                if 'data' in response_data and 'sdGenerationJob' in response_data['data']:
                    return response_data['data']['sdGenerationJob']['generationId']
                else:
                    print("Unexpected JSON structure:", response_data)
                    return None
    except aiohttp.ClientError as e:
        print(f"Error creating generation job: {e}")
        return None
    except (KeyError, TypeError) as e:
        print(f"Error parsing JSON response: {e}")
        return None

async def get_generation_feed(api_key, user_id):
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'dnt': '1',
        'origin': 'https://app.leonardo.ai',
        'priority': 'u=1, i',
        'referer': 'https://app.leonardo.ai/',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'authorization': f'Bearer {api_key}'
    }
    
    query = """
    query GetAIGenerationFeed($where: generations_bool_exp = {}, $userId: uuid, $limit: Int, $offset: Int = 0) {
      generations(
        limit: $limit
        offset: $offset
        order_by: [{createdAt: desc}]
        where: $where
      ) {
        id
        status
        generated_images {
          url
          __typename
        }
        __typename
      }
    }
    """
    
    data = {
        "operationName": "GetAIGenerationFeed",
        "variables": {
            "where": {
                "userId": {
                    "_eq": user_id
                },
                "teamId": {
                    "_is_null": True
                },
                "canvasRequest": {
                    "_eq": False
                },
                "isStoryboard": {
                    "_eq": False
                },
                "source": {
                    "_neq": "LIGHTNING_STREAM"
                },
                "_not": {
                    "_and": [
                        {
                            "modelId": {
                                "_is_null": True
                            },
                            "prompt": {
                                "_neq": ""
                            },
                            "scheduler": {
                                "_is_null": True
                            },
                            "seed": {
                                "_is_null": False
                            },
                            "tiling": {
                                "_is_null": True
                            }
                        }
                    ]
                },
                "universalUpscaler": {
                    "_is_null": True
                }
            },
            "offset": 0,
            "limit": 20  # Increased limit to ensure we get new generation
        },
        "query": query
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_ENDPOINT, headers=headers, json=data) as response:
                response.raise_for_status()
                response_data = await response.json()
                return response_data['data']['generations']
    except aiohttp.ClientError as e:
        print(f"Error getting generation feed: {e}")
        return []
    except (KeyError, TypeError) as e:
        print(f"Error parsing JSON response: {e}")
        return []

async def download_image(url, filename):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.read()
                
                with open(filename, 'wb') as f:
                    f.write(data)
                    
                print(f"Image downloaded: {filename}")
                return True
    except aiohttp.ClientError as e:
        print(f"Error downloading image: {e}")
        return False

async def poll_generation_status(api_key, user_id, generation_id):
    start_time = time.time()
    
    while True:
        generations = await get_generation_feed(api_key, user_id)
        
        for generation in generations:
            if generation['id'] == generation_id:
                if generation['status'] == "COMPLETE":
                    print(f"Generation {generation_id} completed.")
                    return generation
                else:
                    print(f"Generation {generation_id} status: {generation['status']}")
                    break
        else:
            print(f"Generation {generation_id} not found in feed yet.")
            
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_WAIT_TIME:
            print(f"Timeout: Generation {generation_id} did not complete within {MAX_WAIT_TIME} seconds.")
            return None
            
        await asyncio.sleep(POLL_INTERVAL)

async def process_project(api_key, user_id, project):
    project_id = project.get('id')
    prompt = project.get('cover_image_prompt')
    
    if not prompt:
        print(f"Warning: No 'cover_image_prompt' found for project ID {project_id}.")
        return
        
    print(f"Generating image for project ID: {project_id}")
    
    generation_id = await create_generation_job(api_key, prompt)
    if not generation_id:
        print(f"Failed to create generation job for project ID {project_id}.")
        return
        
    print(f"Generation ID: {generation_id}")
    
    # Start polling for generation status
    target_generation = await poll_generation_status(api_key, user_id, generation_id)
    
    if not target_generation:
        print(f"Failed to wait for generation completion for project ID {project_id}.")
        return
        
    image_urls = [img['url'] for img in target_generation['generated_images']]
    
    for url in image_urls:
        filename = os.path.join(IMAGE_SAVE_DIR, f"{project_id}.jpg")
        await download_image(url, filename)

def load_projects_from_json(json_path):
    try:
        with open(json_path, 'r') as f:
            projects = json.load(f)
        return projects
    except FileNotFoundError:
        print(f"Error: File not found: {json_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file: {json_path}")
        return None

# --- Main Code ---
async def main():
    api_key = await get_access_token()
    if not api_key:
        print("Failed to retrieve access token.")
        return
        
    user_id = os.getenv('USER_ID')
    if not user_id:
        print("Error: USER_ID not found in .env file.")
        return
        
    projects = load_projects_from_json(PROJECTS_JSON_PATH)
    if not projects:
        print("Failed to load projects from JSON.")
        return
        
    if not os.path.exists(IMAGE_SAVE_DIR):
        os.makedirs(IMAGE_SAVE_DIR)
    
    # Process all projects concurrently
    tasks = [process_project(api_key, user_id, project) for project in projects]
    await asyncio.gather(*tasks)
    
    print("All image generation tasks completed.")

if __name__ == "__main__":
    asyncio.run(main())
