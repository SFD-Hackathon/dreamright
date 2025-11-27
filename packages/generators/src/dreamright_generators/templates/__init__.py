"""Jinja2 prompt templates for DreamRight."""

from jinja2 import Environment, BaseLoader

# Create Jinja2 environment
env = Environment(
    loader=BaseLoader(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_str: str, **kwargs) -> str:
    """Render a template string with the given context."""
    template = env.from_string(template_str)
    return template.render(**kwargs)
