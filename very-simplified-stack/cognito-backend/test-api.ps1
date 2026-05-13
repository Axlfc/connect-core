$body = @{
    prompt = "¿Quién descubrió América?"
    session_id = "abc"
    parameters = @{}
} | ConvertTo-Json -Depth 10 -Compress

# Forzar codificación UTF-8 (importante para algunos backends)
$utf8Body = [System.Text.Encoding]::UTF8.GetBytes($body)

Invoke-RestMethod -Uri "http://localhost:8000/api/agent" -Method Post -Body $utf8Body -ContentType "application/json; charset=utf-8"