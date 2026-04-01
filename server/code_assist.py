"""
Code Assistant — Active window monitoring + AST context extraction.
Gathers: active window title, clipboard code snippet, Python symbol map.
"""
import ast
import platform
import subprocess
from typing import Optional


def get_active_window_title() -> Optional[str]:
    try:
        if platform.system() == "Windows":
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd) or None
        elif platform.system() == "Linux":
            r = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout.strip() or None
        elif platform.system() == "Darwin":
            r = subprocess.run(
                [
                    "osascript", "-e",
                    'tell application "System Events" to get name of '
                    "first application process whose frontmost is true",
                ],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout.strip() or None
    except Exception:
        return None


def get_clipboard_text() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


def parse_python_symbols(code: str) -> str:
    """Extract top-level symbols from Python source via AST."""
    try:
        tree = ast.parse(code)
        symbols = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                symbols.append(f"def {node.name}({', '.join(args)})")
            elif isinstance(node, ast.AsyncFunctionDef):
                args = [a.arg for a in node.args.args]
                symbols.append(f"async def {node.name}({', '.join(args)})")
            elif isinstance(node, ast.ClassDef):
                symbols.append(f"class {node.name}")
        return "\n".join(symbols) if symbols else "No recognisable symbols."
    except SyntaxError:
        return "Not valid Python syntax."
    except Exception as e:
        return f"AST error: {e}"


def get_code_context() -> str:
    """Build a full code context string for injection into the brain."""
    parts = []

    title = get_active_window_title()
    if title:
        parts.append(f"Active Window: {title}")

    clip = get_clipboard_text().strip()
    if len(clip) > 10:
        preview = clip[:2000] + ("…" if len(clip) > 2000 else "")
        parts.append(f"Clipboard:\n```\n{preview}\n```")

        # Only AST-parse if it looks like Python
        if any(kw in clip for kw in ("def ", "class ", "import ", "from ", "async ")):
            symbols = parse_python_symbols(clip)
            parts.append(f"Symbol Map:\n{symbols}")

    return "\n\n".join(parts) if parts else "No code context available."
