# Research: Total Shell Control Architecture

To turn Son into a true "10x AI Engineer", he needs the ability to execute, read, and retain context within the terminal (e.g. running `npm install`, navigating directories with `cd`, or deploying via Git).

Currently, Son uses atomic Shell triggers (`subprocess.run()`), meaning every command is run in isolation and instantly forgets its environment context (you can't `cd` into a directory and then run a script in the next step). 

Here is the architectural plan to give Son total programmatic shell control. **No code has been implemented yet based on your instructions.**

## 1. The Persistent Subprocess Daemon
To solve the amnesia problem, we will spawn a continuous, background terminal environment when Son boots up:

```python
import subprocess

shell = subprocess.Popen(
    ["powershell.exe", "-NoProfile", "-Command", "-"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)
```
- By booting `powershell.exe` dynamically in `server/system_control.py` using `Popen`, the process stays alive endlessly.

## 2. Asynchronous I/O reading
Because standard output (`stdout`) can block endlessly if a script hangs, we must run non-blocking threads to read the shell output dynamically in real-time. 
- We will pipe this output into a buffer that Son can request, allowing him to see exactly what is on the screen (like a real developer looking at a terminal).

## 3. The `[SHELL: "cmd"]` Action Tag Overhaul
When the LLM generates `[SHELL: "npm run dev"]`, the backend will no longer use standard `os.system()` tricks. 
Instead, it will pipe it natively into the persistent daemon:
```python
shell.stdin.write("npm run dev\n")
shell.stdin.flush()
```
- A custom delimiter (e.g. `echo [CMD_DONE]`) will be injected after every command so the backend knows exactly when the command finishes streaming output.

## 4. Timeout & Failsafes
If Son accidentally runs a command that gets stuck (e.g., `python -m http.server`), the shell will block. 
- We will institute a strict `TIMEOUT_MS` parameter. If a process takes longer than 15 seconds, Son receives an API callback saying `"Process is running in background"`. He can then choose to kill it with a special tag `[SHELL_KILL]`.

## Next Steps
When you are ready to give Son full OS-level dominance, I will integrate this `persistent_shell.py` module into the WebSocket backend and give him the tools to write, compile, and run code entirely on his own.
