from django import template
from django.utils.safestring import mark_safe
import markdown

# This registers the custom filters with Django
register = template.Library()

@register.filter(name='render_md')
def render_md(text):
    if not text:
        return ""
    
    # We include 'fenced_code' to ensure ```python code blocks are parsed properly!
    parsed_html = markdown.markdown(text, extensions=['fenced_code'])
    
    return mark_safe(parsed_html)