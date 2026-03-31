import subprocess
import os
import platform
import pyperclip

def search_web(query: str, max_results: int = 3) -> str:
    """Perform a web search using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        results = ""
        for i, res in enumerate(DDGS().text(query, max_results=max_results)):
            results += f"[{i+1}] {res['title']}: {res['body']}\n"
        return results if results else "No results found."
    except ImportError:
        return "Search failed: DuckDuckGo module not installed."
    except Exception as e:
        return f"Search failed: {e}"

def execute_shell(command: str) -> str:
    """Invokes system shell directly using BASH or CMD."""
    try:
        # We enforce a timeout so Zee doesn't freeze the system
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        
        final_out = ""
        if out: final_out += f"STDOUT:\n{out}\n"
        if err: final_out += f"STDERR:\n{err}\n"
        
        return final_out if final_out else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 seconds."
    except Exception as e:
        return f"Failed to execute shell command: {e}"

def execute_python_cmd(code: str) -> str:
    try:
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            exec(code)
        output = f.getvalue()
        return f"Execution successful. Output: {output}"
    except Exception as e:
        return f"Execution failed: {e}"

def launch_app(app_name: str) -> str:
    """Launch an application logically via explicit mapping, Start Menu, or Shell."""
    app_lower = app_name.lower().strip()
    try:
        if platform.system() == "Windows":
            # Map robust explicit executable names
            shortcuts = {
                "chrome": "chrome.exe",
                "google chrome": "chrome.exe",
                "browser": "start https://google.com",
                "edge": "msedge.exe",
                "antigravity": "cmd /c start .venv\\Scripts\\python.exe main.py",
                "python": "python.exe",
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "explorer": "explorer.exe"
            }
            
            if app_lower in shortcuts:
                cmd = shortcuts[app_lower]
                if cmd.startswith("start") or cmd.startswith("cmd"):
                    subprocess.Popen(cmd, shell=True)
                else:
                    os.startfile(cmd)
                return f"Successfully launched {app_name}."
                
            # Scan Start Menu
            paths_to_search = [
                os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
            ]
            for path in paths_to_search:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file.endswith(".lnk") and app_lower in file.lower() and "uninstall" not in file.lower():
                            target = os.path.join(root, file)
                            try:
                                os.startfile(target)
                                return f"Successfully launched {app_name} via Start Menu shortcut."
                            except Exception:
                                pass
            
            # Fallback
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return f"Initiated {app_name} via OS generic runner."
        else:
            return "App launching only supported on Windows currently."
    except Exception as e:
        return f"Failed to launch app: {e}"

def read_clipboard() -> str:
    return pyperclip.paste()

def write_clipboard(text: str) -> str:
    pyperclip.copy(text)
    return "Clipboard updated."

def browse_url(url: str) -> str:
    """Uses Selenium to interactively load and parse text from a dynamic website."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920x1080")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(10)
        driver.get(url)
        
        title = driver.title
        text_content = driver.find_element("tag name", "body").text
        driver.quit()
        
        # Truncate text context to prevent LLM memory overflow
        if len(text_content) > 3000:
            text_content = text_content[:3000] + "... [TRUNCATED]"
            
        return f"Scraped Page '{title}':\n\n{text_content}"
    except Exception as e:
        return f"Selenium browser failed to load page: {e}"
