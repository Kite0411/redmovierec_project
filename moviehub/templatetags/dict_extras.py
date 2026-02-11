from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    # Be defensive: templates may pass None or a non-dict value.
    try:
        if dictionary is None:
            return ''
        # If the object supports `get`, use it, otherwise try dictionary-like access
        if hasattr(dictionary, 'get'):
            return dictionary.get(key, '')
        # Fallback: try indexing (e.g., when dictionary is actually a list)
        try:
            return dictionary[key]
        except Exception:
            return ''
    except Exception:
        return ''