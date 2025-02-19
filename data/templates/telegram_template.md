{{ emoji }} <b>{{ project_name }}</b> | {{ language }}
<br>
🎯 <b>Primary Use Case:</b>
{{ primary_use_case }}
<br>
✨ <b>Key Features:</b>
{% for feature in key_features|slice(5) %}
• {{ feature }}
{% endfor %}
<br>
📖 <b>Summary:</b>
{{ readme_summary }}
<br>
🔗 <b>Links:</b>
• <a href="{{ url }}?embed=0">View Project</a>
{% if homepage %}
• <a href="{{ homepage }}?embed=0">Homepage</a>
{% endif %}

================
{{ additional_channels }}