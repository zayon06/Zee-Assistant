@echo off
echo ==============================================
echo Installing PyInstaller...
.venv\Scripts\pip install pyinstaller

echo.
echo Cleaning old builds...
rmdir /s /q build dist
del /q zee_entry.spec

echo.
echo Compiling executable...
.venv\Scripts\python -m PyInstaller --clean --onefile ^
    --console ^
    --name Zee-buddy ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols ^
    --hidden-import=uvicorn.protocols.http ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.lifespan ^
    --hidden-import=uvicorn.lifespan.on ^
    --hidden-import=websockets.legacy ^
    --hidden-import=websockets.legacy.server ^
    --hidden-import=websockets.legacy.client ^
    --hidden-import=customtkinter ^
    --hidden-import=pynput.keyboard._win32 ^
    --hidden-import=pynput.mouse._win32 ^
    zee_entry.py

echo.
echo Copying .env file to dist folder so it can be customized alongside the exe...
copy .env dist\.env

echo.
echo ==============================================
echo Build Complete! Your executable is in the /dist/ folder.
echo ==============================================
