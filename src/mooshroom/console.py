from rich.console import Console
from rich.theme import Theme

theme = Theme({"info": "dim", "warning": "yellow"})

console = Console(theme=theme, highlight=False)
