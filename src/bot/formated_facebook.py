import json
import os
import logging
import random
import re
import html
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
from jinja2 import Environment, FileSystemLoader

# Configure logging to console only
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ])

MAX_FB_POST_LENGTH = 2000  # Facebook post character limit
DEFAULT_LANGUAGE_EMOJI = "💻"

# Enhanced emoji map with more languages and frameworks
TECH_EMOJI_MAP = {
    "python": "🐍",
    "javascript": "📜",
    "typescript": "📘",
    "java": "☕",
    "c#": "🔷",
    "c++": "🔨",
    "c": "⚙️",
    "go": "🐹",
    "rust": "🦀",
    "php": "🐘",
    "ruby": "💎",
    "swift": "🍎",
    "kotlin": "🤖",
    "scala": "🔶",
    "r": "📊",
    "dart": "🎯",
    "flutter": "🦋",
    "html": "🌐",
    "css": "🎨",
    "shell": "🐚",
    "bash": "🐚",
    "powershell": "💻",
    "sql": "🗄️",
    "jupyter": "📓",
    "vue": "🟢",
    "react": "⚛️",
    "angular": "🅰️",
    "node": "📦",
    "django": "🎸",
    "flask": "🧪",
    "spring": "🍃",
    "laravel": "🔺",
    "rails": "🚂",
    "unity": "🎮",
    "unreal": "🎯",
    "tensorflow": "🧠",
    "pytorch": "🔥",
    "kubernetes": "🚢",
    "docker": "🐳",
    "aws": "☁️",
    "azure": "☁️",
    "gcp": "☁️",
    "android": "📱",
    "ios": "📱",
    "linux": "🐧",
    "windows": "🪟",
    "macos": "🍏",
    "blockchain": "⛓️",
    "web3": "🌐"
}

# Enhanced feature icons for better visualization
FEATURE_ICON = "✅"

# Enhanced dividers with more variety
DIVIDERS = [
    "━━━━━━━━━━━━━━━━━━━━━━━━",
    "┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅┅",
    "╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍",
    "┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉",
    "╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌",
    "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯",
    "⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃⁃",
    "⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆⋆",
    "✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧✧",
    "⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬⚬",
    "•••••••••••••••••••••••",
    "◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦◦",
    "▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪",
    "▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫",
    "◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈",
    "◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇◇",
    "♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦♦",
    "❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖❖",
    "✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦✦",
    "✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱✱",
    "❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂❂",
    "✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿✿",
    "❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀❀",
    "◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉◉"
]

# Theme colors for different programming languages
LANGUAGE_THEMES = {
    "python": ("🐍", "#3776AB", "Python"),
    "javascript": ("📜", "#F7DF1E", "JavaScript"),
    "typescript": ("📘", "#3178C6", "TypeScript"),
    "java": ("☕", "#007396", "Java"),
    "c#": ("🔷", "#239120", "C#"),
    "c++": ("🔨", "#00599C", "C++"),
    "go": ("🐹", "#00ADD8", "Go"),
    "rust": ("🦀", "#DEA584", "Rust"),
    "php": ("🐘", "#777BB4", "PHP"),
    "ruby": ("💎", "#CC342D", "Ruby"),
    "swift": ("🍎", "#FA7343", "Swift"),
    "kotlin": ("🤖", "#7F52FF", "Kotlin"),
    "scala": ("🔶", "#DC322F", "Scala"),
    "r": ("📊", "#276DC3", "R"),
    "dart": ("🎯", "#0175C2", "Dart")
}

def to_bold(text: str) -> str:
    """Convert regular text to Unicode bold text."""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    bold = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    result = ""
    for char in text:
        idx = normal.find(char)
        if idx != -1:
            result += bold[idx]
        else:
            result += char
    return result

def to_fancy(text: str) -> str:
    """Convert text to fancy Unicode characters."""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    fancy = "𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    result = ""
    for char in text:
        idx = normal.find(char)
        if idx != -1:
            result += fancy[idx]
        else:
            result += char
    return result

def get_random_divider() -> str:
    """Return a random decorative divider."""
    return random.choice(DIVIDERS)

def get_tech_emoji(language: str) -> str:
    """Return appropriate emoji for the programming language."""
    if not language:
        return DEFAULT_LANGUAGE_EMOJI
    language = language.lower()
    for key, emoji in TECH_EMOJI_MAP.items():
        if key in language:
            return emoji
    return DEFAULT_LANGUAGE_EMOJI

def get_language_theme(language: str) -> Tuple[str, str, str]:
    """Return theme information (emoji, color, formatted name) for a language."""
    if not language:
        return (DEFAULT_LANGUAGE_EMOJI, "#808080", "Unknown")
    language_lower = language.lower()
    for key, (emoji, color, name) in LANGUAGE_THEMES.items():
        if key in language_lower:
            return (emoji, color, name)
    return (DEFAULT_LANGUAGE_EMOJI, "#808080", language)

def clean_text(text: str) -> str:
    """Clean and sanitize text."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to maximum length while preserving words."""
    if not text or len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."

def normalize_list(data: Union[str, List, None]) -> List:
    """Convert various input formats to a normalized list."""
    if not data:
        return []
    if isinstance(data, str):
        try:
            # Try to evaluate if it looks like a Python list
            if data.strip().startswith('[') and data.strip().endswith(']'):
                return eval(data)
            return [data]
        except (SyntaxError, NameError):
            return [data]
    if isinstance(data, list):
        # Handle nested lists
        if data and isinstance(data[0], list):
            return data[0]
        return data
    return []

def get_star_rating(stars: int) -> str:
    """Generate a visual star rating based on number of stars."""
    if stars < 10:
        return "⭐"
    elif stars < 100:
        return "⭐⭐"
    elif stars < 1000:
        return "⭐⭐⭐"
    elif stars < 10000:
        return "⭐⭐⭐⭐"
    else:
        return "⭐⭐⭐⭐⭐"

def format_number(num: int) -> str:
    """Format a number with thousand separators and abbreviations for large numbers."""
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num/1000:.1f}K".replace('.0K', 'K')
    else:
        return f"{num/1000000:.1f}M".replace('.0M', 'M')

def get_trending_indicator(stars: int, forks: int) -> str:
    """Generate a trending indicator based on stars and forks ratio."""
    if not stars or not forks:
        return ""
    ratio = stars / forks
    if ratio > 10:
        return "🔥 Super Hot!"
    elif ratio > 7:
        return "🌟 Rising Fast!"
    elif ratio > 5:
        return "📈 Growing!"
    elif ratio > 3:
        return "✨ Notable!"
    else:
        return "🔍 Worth a Look"


def format_facebook_post(project: Dict[str, Any], template_env: Environment) -> Optional[Dict[str, Any]]:
    """Format a project into a Facebook post."""
    try:
        project_id = project.get("id", "unknown")
        project_name = project.get("name", "Unknown Project")

        # Skip projects without media
        if not project.get("media_urls"):
            logging.info(f"Skipping project {project_id} ({project_name}): no media")
            return None

        template = template_env.get_template("facebook_template.md")

        # Normalize key features and clean them
        key_features = normalize_list(project.get("key_features", []))
        key_features = [clean_text(feature) for feature in key_features if feature]

        # Ограничить количество ключевых характеристик до 15
        key_features = key_features[:15]

        # Process topics (tags)
        topics = normalize_list(project.get("topics", []))
        pattern = r'[^\w]'
        topics = [f"#{re.sub(pattern, '_', str(t))}" for t in topics[:5]]  # Limit to 5 tags


        # Normalize language
        language = project.get("language", "Not specified")
        if isinstance(language, list):
            language = ', '.join(language)

        # Get tech emoji and theme
        tech_emoji = get_tech_emoji(language)
        lang_emoji, lang_color, lang_name = get_language_theme(language)

        # Generate random divider
        divider = get_random_divider()

        # Process stars and forks
        stars = project.get("stars", 0)
        forks = project.get("forks", 0)
        star_rating = get_star_rating(stars)
        trending = get_trending_indicator(stars, forks)

        # Clean and truncate readme summary
        readme_summary = clean_text(project.get("readme_summary", "Not available"))
        readme_summary = truncate_text(readme_summary, 500)

        # Generate creation date info
        created_at = project.get("created_at")
        updated_at = project.get("updated_at")

        creation_info = ""
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                creation_info = f"Created: {created_date.strftime('%b %Y')}"

                if updated_at:
                    updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    creation_info += f" • Updated: {updated_date.strftime('%b %Y')}"
            except (ValueError, TypeError):
                pass

        # Prepare context for template
        context = {
            "project_name": project_name,
            "language": language,
            "tech_emoji": tech_emoji,
            "lang_emoji": lang_emoji,
            "lang_color": lang_color,
            "lang_name": lang_name,
            "primary_use_case": clean_text(project.get("primary_use_case", "Not specified")),
            "readme_summary": readme_summary,
            "key_features": key_features,
            "stars": format_number(stars),
            "stars_raw": stars,
            "forks": format_number(forks),
            "forks_raw": forks,
            "open_issues": format_number(project.get("open_issues", 0)),
            "star_rating": star_rating,
            "trending": trending,
            "url": project.get("url", ""),
            "topics": topics,
            "creation_info": creation_info,
            "bold": to_bold,
            "fancy": to_fancy,
            "divider": divider,
            "get_feature_icon": lambda _: FEATURE_ICON,
            "current_year": datetime.now().year
        }

        # Render template
        content = template.render(context)

        # Trim key_features if content is too long
        while len(content) > MAX_FB_POST_LENGTH and key_features:
            key_features.pop()
            context["key_features"] = key_features
            content = template.render(context)

        if len(content) > MAX_FB_POST_LENGTH:
            logging.warning(f"Skipping project {project_id} ({project_name}): Content too long even after trimming")
            return None

        if not key_features:
            logging.warning(f"Skipping project {project_id} ({project_name}): No key features left after trimming")
            return None

        return {
            "content": content,
            "media_urls": project.get("media_urls", [])
        }

    except Exception as e:
        logging.error(f"Error formatting post for project {project.get('id', 'unknown')} ({project.get('name', 'unknown')}): {str(e)}")
        return None

def main():
    """Main function to process projects and generate Facebook posts."""
    start_time = datetime.now()
    logging.info(f"Starting Facebook post generation at {start_time}")

    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Load projects data
        try:
            with open("data/projects.json", "r", encoding="utf-8") as f:
                projects = json.load(f)
        except FileNotFoundError:
            logging.error("File data/projects.json not found")
            return
        except json.JSONDecodeError:
            logging.error("Invalid JSON format in data/projects.json")
            return

        if not projects:
            logging.info("No projects found in data file")
            return

        # Initialize template environment
        try:
            template_env = Environment(loader=FileSystemLoader("data/templates"))
            # Verify template exists
            template_env.get_template("facebook_template.md")
        except Exception as e:
            logging.error(f"Template error: {str(e)}")
            return

        # Process projects
        posts = []
        skipped = 0

        for i, project in enumerate(projects):
            logging.info(f"Processing project {i+1}/{len(projects)}: {project.get('name', 'Unknown')}")
            post = format_facebook_post(project, template_env)
            if post:
                posts.append({
                    "project_id": project.get("id", "unknown"),
                    "content": post["content"],
                    "platform": "facebook",
                    "media_urls": post["media_urls"],
                    "processed_at": datetime.now().isoformat()
                })
            else:
                skipped += 1

        # Save results to facebook_posts.json
        if posts:
            try:
                with open("data/facebook_posts.json", "w", encoding="utf-8") as f:
                    json.dump(posts, f, indent=4, ensure_ascii=False)
                logging.info(f"Successfully saved {len(posts)} Facebook posts to facebook_posts.json")

            except Exception as e:
                logging.error(f"Error saving posts: {str(e)}")
        else:
            logging.warning("No valid posts were generated")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logging.info(f"Finished processing at {end_time}")
        logging.info(f"Total duration: {duration:.2f} seconds")
        logging.info(f"Processed {len(projects)} projects: {len(posts)} successful, {skipped} skipped")

    except Exception as e:
        logging.error(f"Unexpected error in main function: {str(e)}")

if __name__ == "__main__":
    main()
