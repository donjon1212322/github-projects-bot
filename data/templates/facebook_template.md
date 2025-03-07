{{ bold(project_name.upper()) }} | {{ primary_use_case }}  {{ trending }}

{{ divider }}

{{ bold("TECH STACK") }}: {{ lang_emoji }} {{ language }} 
🎯 {{ bold("USE CASE") }}: {{ primary_use_case }}
{% if creation_info %}📅 {{ creation_info }}{% endif %}

{{ divider }}

✨ {{ bold("KEY FEATURES") }} ✨

{% for feature in key_features -%}
✅ {{ feature }}
{% endfor %}

{{ divider }}

📊 {{ bold("PROJECT STATS") }}

{{ star_rating }} {{ stars }} {{ bold("stars") }}
🍴 {{ forks }} {{ bold("forks") }}
🔍 {{ open_issues }} {{ bold("open issues") }}

{{ divider }}

📝 {{ bold("ABOUT THIS PROJECT") }}

{{ readme_summary }}

{{ divider }}

🔗 {{ bold("LINKS") }}
• {{ bold("GitHub") }}: {{ url }}

{{ divider }}

🔥 {{ bold("Follow us") }} for daily GitHub projects!
👉 GitHub Open Source: https://t.me/GitHub_Open_Source

{{ divider }}

{% if topics %}
🏷️ {{ bold("TAGS") }}
{{ topics | join(' ') }}
{% endif %}

© {{ current_year }} - Curated with ❤️ for developers
