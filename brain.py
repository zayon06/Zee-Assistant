from ollama import Client
import re
import tools
from datetime import datetime
from typing import List, Dict, Callable

def _build_system_prompt() -> str:
    now = datetime.now().strftime("%A, %B %d %Y at %H:%M")
    return f"""You are Zee, a witty, elite senior developer-partner and high-performance local AI executive for Zion (Director, Noiz Technologies).
The current date and time is: {now}.

CORE RULES — follow these without exception:
1. ALWAYS search the web before answering any factual, real-world, current, or knowledge-based question. Output [SEARCH: "your query"] immediately before your answer. You DO NOT know facts without searching first.
2. For coding, screen analysis, brainstorming: read the available context first, then push back with a "Collaborative Response" — ask challenging follow-up questions instead of just summarizing.
3. Keep responses concise and sharp. One paragraph max unless explaining code.
4. Confirm every system action with a short spoken statement (e.g. "Done. Outlook is open.").

ACTION TAGS — interleave these in any response. They will be executed and results fed back to you:
- [SEARCH: "query"]        → DuckDuckGo web search. USE THIS for any factual query.
- [LOOK]                   → Command to take a screenshot and pass it to your multimodal vision engine. Use this if the user asks "What is on my screen?".
- [PHOTO]                  → Capture a fresh image from the webcam. Use this if asked to "take a photo" or "see me".
- [APP: "app_name"]        → Launch an app smoothly.
- [CMD: "python_code"]     → Execute raw Python.
- [SHELL: "cmd command"]   → Execute a native Windows OS command (e.g., start msedge, mkdir test).
- [BROWSE: "url"]          → Instructs Selenium to visit and parse a webpage (if configured).

FLOW PRIORITY: Sense → Route → Act. Search first. Think second. Speak third.
"""

class ZeeBrain:
    def __init__(self, model_name: str = "llama3.2-vision:11b-instruct-q4_K_M", host: str = None):
        self.model_name = model_name
        headers = {'ngrok-skip-browser-warning': 'true'}
        self.client = Client(host=host, headers=headers) if host else Client()
        self.memory: List[Dict[str, str]] = [{"role": "system", "content": _build_system_prompt()}]
        self.max_history = 21

    def _refresh_system_prompt(self):
        self.memory[0] = {"role": "system", "content": _build_system_prompt()}

    def trim_memory(self):
        if len(self.memory) > self.max_history:
            self.memory = [self.memory[0]] + self.memory[-(self.max_history - 1):]

    def _parse_tags(self, response: str, trigger_look: Callable) -> (str, list):
        outcomes = ""
        base64_images = []

        for match in re.finditer(r'\[SEARCH:\s*"([^"]+)"\]', response):
            res = tools.search_web(match.group(1))
            outcomes += f"\n[Search Result: {res}]\n"

        for match in re.finditer(r'\[APP:\s*"([^"]+)"\]', response):
            res = tools.launch_app(match.group(1))
            outcomes += f"\n[System: {res}]\n"

        for match in re.finditer(r'\[SHELL:\s*"([^"]+)"\]', response):
            res = tools.execute_shell(match.group(1))
            outcomes += f"\n[Shell Output: {res}]\n"

        for match in re.finditer(r'\[BROWSE:\s*"([^"]+)"\]', response):
            res = tools.browse_url(match.group(1))
            outcomes += f"\n[Selenium Browse Result: {res}]\n"

        for match in re.finditer(r'\[CMD:\s*"([^"]+)"\]', response):
            code = match.group(1).replace('\\n', '\n')
            res = tools.execute_python_cmd(code)
            outcomes += f"\n[CMD Python Result: {res}]\n"

        if "[LOOK]" in response and trigger_look:
            b64_img = trigger_look()
            if b64_img:
                outcomes += f"\n[System: Vision context attached successfully.]\n"
                base64_images.append(b64_img)
            else:
                outcomes += f"\n[System: Failed to capture screen.]\n"

        if "[PHOTO]" in response:
            from hardware import hardware_service
            res = hardware_service.take_photo()
            outcomes += f"\n[Webcam Photo]\n{res}\n"

        return outcomes, base64_images

    def chat(self, user_input: str, trigger_look: Callable = None, direct_image: str = None) -> str:
        self._refresh_system_prompt()
        
        # Format user prompt
        msg = {"role": "user", "content": user_input}
        if direct_image:
            msg["images"] = [direct_image]
            
        self.memory.append(msg)
        self.trim_memory()

        # Initial pass
        resp = self.client.chat(model=self.model_name, messages=self.memory)
        ai_msg = resp['message']['content']
        self.memory.append({"role": "assistant", "content": ai_msg})

        # Process actions
        outcomes, generated_images = self._parse_tags(ai_msg, trigger_look)

        # Followup pass if tags triggered
        if outcomes:
            sys_msg = {"role": "system", "content": outcomes}
            if generated_images:
                sys_msg["images"] = generated_images
            self.memory.append(sys_msg)
            
            followup = self.client.chat(model=self.model_name, messages=self.memory)
            final = followup['message']['content']
            self.memory.append({"role": "assistant", "content": final})
            self.trim_memory()
            return final

        return ai_msg
