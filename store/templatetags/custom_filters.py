from django import template

register = template.Library()

@register.filter
def endswith(value, arg):
    """Prüft, ob ein String mit einem bestimmten Suffix endet"""
    return str(value).lower().endswith(arg.lower())
