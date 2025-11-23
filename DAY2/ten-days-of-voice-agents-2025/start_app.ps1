$root = "c:\Myspace\Codes\MURFAI\10dayschallenge\MAIN\DAY2\ten-days-of-voice-agents-2025"

Write-Host "Starting LiveKit Server..."
Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", "livekit-server --dev"
Start-Sleep -Seconds 2

Write-Host "Starting Backend Agent..."
Start-Process powershell -WorkingDirectory "$root\backend" -ArgumentList "-NoExit", "-Command", "uv run python src/agent.py dev"
Start-Sleep -Seconds 2

Write-Host "Starting Frontend..."
Start-Process powershell -WorkingDirectory "$root\frontend" -ArgumentList "-NoExit", "-Command", "pnpm dev"

Write-Host "All services started. Opening browser..."
Start-Sleep -Seconds 5
Start-Process "http://localhost:3000"
