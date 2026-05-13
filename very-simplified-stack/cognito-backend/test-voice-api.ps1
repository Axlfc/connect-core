# ═══════════════════════════════════════════════════════════════════
#  Cognito Stack — PowerShell Profile
#  Incluye: Invoke-Cognito (texto) + Invoke-CognitoTTS (voz)
#  Aliases: cog / cogt
# ═══════════════════════════════════════════════════════════════════

# ── Spinner C# (compartido, se compila una sola vez) ─────────────
$_cognitoSpinnerCode = @"
using System;
using System.Threading;

public class CognitoSpinner {
    private string[] _frames;
    private volatile bool _stop = false;
    private Thread _thread;

    public CognitoSpinner(string[] frames) { _frames = frames; }

    public void Start() {
        _thread = new Thread(() => {
            int i = 0;
            while (!_stop) {
                Console.Write("\r" + _frames[i % _frames.Length]);
                Thread.Sleep(55);
                i++;
            }
        });
        _thread.IsBackground = true;
        _thread.Start();
    }

    public void Stop() {
        _stop = true;
        if (_thread != null) _thread.Join(400);
        Console.Write("\r" + new string(' ', 52) + "\r");
    }
}
"@
if (-not ([System.Management.Automation.PSTypeName]'CognitoSpinner').Type) {
    Add-Type -TypeDefinition $_cognitoSpinnerCode -Language CSharp
}

$_cognitoFrames = [string[]]@(
    "  cognito.stack  ◆···············  "
    "  cognito.stack  ·◆··············  "
    "  cognito.stack  ··◆·············  "
    "  cognito.stack  ···◆············  "
    "  cognito.stack  ····◆···········  "
    "  cognito.stack  ·····◆··········  "
    "  cognito.stack  ······◆·········  "
    "  cognito.stack  ·······◆········  "
    "  cognito.stack  ········◆·······  "
    "  cognito.stack  ·········◆······  "
    "  cognito.stack  ··········◆·····  "
    "  cognito.stack  ···········◆····  "
    "  cognito.stack  ············◆···  "
    "  cognito.stack  ·············◆··  "
    "  cognito.stack  ··············◆·  "
    "  cognito.stack  ···············◆  "
    "  cognito.stack  ··············◆·  "
    "  cognito.stack  ·············◆··  "
    "  cognito.stack  ············◆···  "
    "  cognito.stack  ···········◆····  "
    "  cognito.stack  ··········◆·····  "
    "  cognito.stack  ·········◆······  "
    "  cognito.stack  ········◆·······  "
    "  cognito.stack  ·······◆········  "
    "  cognito.stack  ······◆·········  "
    "  cognito.stack  ·····◆··········  "
    "  cognito.stack  ····◆···········  "
    "  cognito.stack  ···◆············  "
    "  cognito.stack  ··◆·············  "
    "  cognito.stack  ·◆··············  "
)

# ── Configuración Global ───────────────────────────────────────────
$script:RESET = [char]27 + "[0m"


function Get-CognitoConfig {
    $config = @{
        UncertaintyThreshold = 0.55
        EnableUncertainty    = $true
        ColorMode            = "full"
    }

    # 1. Cargar desde config.json si existe
    $configPath = Join-Path (Join-Path $env:USERPROFILE ".cognito") "config.json"

    if (Test-Path $configPath) {
        try {
            $json = Get-Content $configPath -Raw | ConvertFrom-Json
            if ($null -ne $json.UncertaintyThreshold) { $config.UncertaintyThreshold = [double]$json.UncertaintyThreshold }
            if ($null -ne $json.EnableUncertainty)    { $config.EnableUncertainty    = [bool]$json.EnableUncertainty }
            if ($null -ne $json.ColorMode)            { $config.ColorMode            = $json.ColorMode }
        } catch {}
    }

    # 2. Cargar desde Variables de Entorno
    if ($null -ne $env:COGNITO_UNCERTAINTY_THRESHOLD) { $config.UncertaintyThreshold = [double]$env:COGNITO_UNCERTAINTY_THRESHOLD }
    if ($null -ne $env:COGNITO_ENABLE_UNCERTAINTY)    { $config.EnableUncertainty    = [bool]$env:COGNITO_ENABLE_UNCERTAINTY }
    if ($null -ne $env:COGNITO_COLOR_MODE)            { $config.ColorMode            = $env:COGNITO_COLOR_MODE }

    return $config
}

function Get-UncertaintyColor {
    param([double]$Score)

    if ($Score -lt 0.5) {
        # blue (100, 200, 255) → amber (255, 200, 60)
        $t = $Score / 0.5
        $r = [int](100 + $t * (255 - 100))
        $g = 200
        $b = [int](255 + $t * (60 - 255))
    } else {
        # amber (255, 200, 60) → red (255, 60, 40)
        $t = ($Score - 0.5) / 0.5
        $r = 255
        $g = [int](200 + $t * (60 - 200))
        $b = [int](60 + $t * (40 - 60))
    }
    return ([char]27 + "[38;2;$r;$g;${b}m")

}

# ═══════════════════════════════════════════════════════════════════
#  Invoke-Cognito — Solo texto, sin TTS
# ═══════════════════════════════════════════════════════════════════
function Invoke-Cognito {
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Prompt,
        [string]$Model     = "cognito",
        [string]$Endpoint  = "http://127.0.0.1:8000/v1/chat/completions",
        [double]$Threshold = -1,
        [switch]$NoColor,
        [switch]$Raw
    )

    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║        COGNITO STACK  //  AI         ║" -ForegroundColor Cyan
    Write-Host "  ║  model: $($Model.PadRight(28))║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    $bodyObj   = [ordered]@{ model = $Model; messages = @(@{ role = "user"; content = $Prompt }); stream = $true }
    $bodyJson  = $bodyObj | ConvertTo-Json -Compress -Depth 5
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

    [System.Net.ServicePointManager]::Expect100Continue = $false
    $request = [System.Net.HttpWebRequest]::Create($Endpoint)
    $request.Method = "POST"; $request.ContentType = "application/json; charset=utf-8"
    $request.ContentLength = $bodyBytes.Length; $request.Timeout = 180000
    $request.ReadWriteTimeout = 180000; $request.KeepAlive = $true
    $request.ServicePoint.Expect100Continue = $false

    try {
        $rs = $request.GetRequestStream(); $rs.Write($bodyBytes, 0, $bodyBytes.Length); $rs.Close()
    } catch { Write-Host "  [Error al enviar request] $_" -ForegroundColor Red; return }

    $spinner = New-Object CognitoSpinner -ArgumentList (,$_cognitoFrames)
    $spinner.Start()

    $firstToken = $true; $fullResponse = ""
    $config = Get-CognitoConfig
    $activeThreshold = if ($Threshold -ge 0) { $Threshold } else { $config.UncertaintyThreshold }
    $useColor = (-not $NoColor) -and ($config.ColorMode -ne "none")

    try {
        $response   = $request.GetResponse()
        $reader     = New-Object System.IO.StreamReader($response.GetResponseStream(), [System.Text.Encoding]::UTF8)

        while (-not $reader.EndOfStream) {
            $line = $reader.ReadLine()
            if (-not $line -or -not $line.StartsWith("data:")) { continue }
            $jsonPart = $line.Substring(5).Trim()
            if ($jsonPart -eq "[DONE]") { break }
            try { $chunk = $jsonPart | ConvertFrom-Json } catch { continue }
            $delta = $chunk.choices[0].delta
            $token = $delta.content
            if ($null -eq $token -or $token -eq "") { continue }
            if ($firstToken) { $spinner.Stop(); Write-Host "  " -NoNewline -ForegroundColor DarkGray; $firstToken = $false }

            if ($useColor -and ($null -ne $delta.uncertainty)) {
                $u = [double]$delta.uncertainty
                if ($config.ColorMode -eq "threshold" -and $u -lt $activeThreshold) {
                    Write-Host $token -NoNewline -ForegroundColor White
                } else {
                    $color = Get-UncertaintyColor $u
                    Write-Host "$color$token$script:RESET" -NoNewline
                }
            } else {
                Write-Host $token -NoNewline -ForegroundColor White
            }

            $fullResponse += $token
        }
        $reader.Close(); $response.Close()
    } catch { $spinner.Stop(); Write-Host "  [Error] $_" -ForegroundColor Red }

    if ($firstToken) { $spinner.Stop() }
    Write-Host ""; Write-Host ""
    Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host ""
    if ($Raw) { return $fullResponse }
}

# ═══════════════════════════════════════════════════════════════════
#  Invoke-CognitoTTS — Texto + voz Kokoro + post-procesado ffmpeg
# ═══════════════════════════════════════════════════════════════════
function Invoke-CognitoTTS {
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Prompt,
        [string]$Model       = "cognito",
        [string]$Endpoint    = "http://127.0.0.1:8000/v1/chat/completions",
        [string]$TTSEndpoint = "http://127.0.0.1:8880/v1/audio/speech",
        [string]$Voice       = "ef_dora",
        [int]$MinPhraseLen   = 60,
        [double]$Threshold   = -1,
        [switch]$NoColor,
        [switch]$NoTTS,
        [switch]$Raw
    )

    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║        COGNITO STACK  //  AI         ║" -ForegroundColor Cyan
    Write-Host "  ║  model: $($Model.PadRight(28))║" -ForegroundColor Cyan
    $ttsLabel = if ($NoTTS) { "off" } else { $Voice }
    Write-Host "  ║  voice: $($ttsLabel.PadRight(28))║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    # ── Limpiar markdown ──────────────────────────────────────────────
    function Clear-Markdown([string]$Text) {
        $t = $Text
        $t = $t -replace '\*\*(.+?)\*\*', '$1'
        $t = $t -replace '\*(.+?)\*',     '$1'
        $t = $t -replace '#{1,6}\s*',     ''
        $t = $t -replace '(?m)^\s*[-*]\s+', ''
        $t = $t -replace '`{1,3}[^`]*`{1,3}', ''
        $t = $t -replace '\[(.+?)\]\(.+?\)', '$1'
        $t = $t -replace '\n+', ' '
        return $t.Trim()
    }

    # ── Post-procesado de voz con ffmpeg ──────────────────────────────
    # Cadena de filtros inspirada en el perfil de voz Cognito:
    #   - highpass 80Hz          → elimina rumble
    #   - eq 170Hz +2.5dB        → fundamental femenino resonante
    #   - eq 340Hz +1.5dB        → armónicos de fondo (330-350Hz)
    #   - eq 3000Hz +1.5dB       → presencia y claridad de vocales
    #   - eq 10000Hz +2dB        → shimmer cristalino (8-12kHz)
    #   - aecho 50ms 15% wet     → reverb sutil
    #   - chorus suave           → iridiscencia / oscilación cuántica
    #   - loudnorm               → normalización final
    $script:_voiceFilters = "highpass=f=80,equalizer=f=170:width_type=o:width=2:g=2.5,equalizer=f=340:width_type=o:width=1.5:g=1.5,equalizer=f=3000:width_type=o:width=1.5:g=1.5,equalizer=f=10000:width_type=o:width=2:g=2,aecho=0.85:0.15:50:0.15,chorus=0.7:0.9:55:0.4:0.25:2,loudnorm"

    function Invoke-TTSPhrase([string]$Text, [string]$Endpoint, [string]$Voice, [double]$Uncertainty = 0.0) {
        $clean = Clear-Markdown $Text
        if ($clean.Length -lt 2) { return }

        try {
            $tmp    = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "cog_raw_$(Get-Random).mp3")
            $tmpFx  = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "cog_fx_$(Get-Random).mp3")

            # 1. Llamar a Kokoro
            $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes(
                ([ordered]@{ input = $clean; voice = $Voice; response_format = "mp3"; stream = $false } | ConvertTo-Json -Compress -Depth 3)
            )
            [System.Net.ServicePointManager]::Expect100Continue = $false
            $req = [System.Net.HttpWebRequest]::Create($Endpoint)
            $req.Method = "POST"; $req.ContentType = "application/json; charset=utf-8"
            $req.ContentLength = $bodyBytes.Length; $req.Timeout = 30000
            $rs = $req.GetRequestStream(); $rs.Write($bodyBytes, 0, $bodyBytes.Length); $rs.Close()
            $resp = $req.GetResponse(); $respStream = $resp.GetResponseStream()
            $fs = [System.IO.File]::Create($tmp)
            $buf = New-Object byte[] 8192
            while (($read = $respStream.Read($buf, 0, $buf.Length)) -gt 0) { $fs.Write($buf, 0, $read) }
            $fs.Close(); $respStream.Close(); $resp.Close()

            # 2. Post-procesar con ffmpeg
            # 🎁 FUTURO: Modulación de audio basada en incertidumbre
            # if ($Uncertainty -gt 0.7) {
            #     # Ejemplo: pitch más bajo o velocidad variable
            # }
            & ffmpeg -y -i $tmp -af $script:_voiceFilters -ar 44100 -ab 192k $tmpFx 2>$null

            # 3. Reproducir con ffplay
            $playFile = if ((Test-Path $tmpFx) -and (Get-Item $tmpFx).Length -gt 1000) { $tmpFx } else { $tmp }
            Start-Process ffplay -ArgumentList "-nodisp", "-autoexit", "-loglevel", "quiet", $playFile -NoNewWindow -Wait

        } catch { <# silencioso #> }
        finally {
            Remove-Item $tmp   -ErrorAction SilentlyContinue
            Remove-Item $tmpFx -ErrorAction SilentlyContinue
        }
    }

    # ── ¿Cortar frase aquí? ───────────────────────────────────────────
    function Should-Flush([string]$Buffer, [int]$MinLen) {
        if ($Buffer.Length -lt $MinLen) { return $false }
        $last = $Buffer[-1]
        if ($last -eq '?' -or $last -eq '!') { return $true }
        if ($last -eq '.') {
            if ($Buffer -match '\b(ej|etc|sr|dra?|ing|vs|fig|num|art)\.$') { return $false }
            if ($Buffer -match '\b\d+\.$')   { return $false }
            if ($Buffer -match '\b[A-Z]\.$') { return $false }
            return $true
        }
        return $false
    }

    # ── HTTP LLM ──────────────────────────────────────────────────────
    $bodyObj   = [ordered]@{ model = $Model; messages = @(@{ role = "user"; content = $Prompt }); stream = $true }
    $bodyJson  = $bodyObj | ConvertTo-Json -Compress -Depth 5
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

    [System.Net.ServicePointManager]::Expect100Continue = $false
    $request = [System.Net.HttpWebRequest]::Create($Endpoint)
    $request.Method = "POST"; $request.ContentType = "application/json; charset=utf-8"
    $request.ContentLength = $bodyBytes.Length; $request.Timeout = 180000
    $request.ReadWriteTimeout = 180000; $request.KeepAlive = $true
    $request.ServicePoint.Expect100Continue = $false

    try {
        $rs = $request.GetRequestStream(); $rs.Write($bodyBytes, 0, $bodyBytes.Length); $rs.Close()
    } catch { Write-Host "  [Error al enviar request] $_" -ForegroundColor Red; return }

    $spinner = New-Object CognitoSpinner -ArgumentList (,$_cognitoFrames)
    $spinner.Start()

    $firstToken = $true; $fullResponse = ""; $phraseBuffer = ""; $lastUncertainty = 0.0
    $config = Get-CognitoConfig
    $activeThreshold = if ($Threshold -ge 0) { $Threshold } else { $config.UncertaintyThreshold }
    $useColor = (-not $NoColor) -and ($config.ColorMode -ne "none")

    try {
        $response = $request.GetResponse()
        $reader   = New-Object System.IO.StreamReader($response.GetResponseStream(), [System.Text.Encoding]::UTF8)

        while (-not $reader.EndOfStream) {
            $line = $reader.ReadLine()
            if (-not $line -or -not $line.StartsWith("data:")) { continue }
            $jsonPart = $line.Substring(5).Trim()
            if ($jsonPart -eq "[DONE]") { break }
            try { $chunk = $jsonPart | ConvertFrom-Json } catch { continue }
            $delta = $chunk.choices[0].delta
            $token = $delta.content
            if ($null -eq $token -or $token -eq "") { continue }

            if ($firstToken) { $spinner.Stop(); Write-Host "  " -NoNewline -ForegroundColor DarkGray; $firstToken = $false }

            if ($useColor -and ($null -ne $delta.uncertainty)) {
                $u = [double]$delta.uncertainty
                $lastUncertainty = $u
                if ($config.ColorMode -eq "threshold" -and $u -lt $activeThreshold) {
                    Write-Host $token -NoNewline -ForegroundColor White
                } else {
                    $color = Get-UncertaintyColor $u
                    Write-Host "$color$token$script:RESET" -NoNewline
                }
            } else {
                Write-Host $token -NoNewline -ForegroundColor White
            }

            $fullResponse  += $token
            $phraseBuffer  += $token

            if (-not $NoTTS -and (Should-Flush $phraseBuffer $MinPhraseLen)) {
                $toSpeak = $phraseBuffer; $phraseBuffer = ""
                Invoke-TTSPhrase $toSpeak $TTSEndpoint $Voice $lastUncertainty
            }
        }

        if (-not $NoTTS -and $phraseBuffer.Trim().Length -gt 2) {
            Invoke-TTSPhrase $phraseBuffer $TTSEndpoint $Voice $lastUncertainty
        }

        $reader.Close(); $response.Close()
    } catch { $spinner.Stop(); Write-Host "  [Error] $_" -ForegroundColor Red }

    if ($firstToken) { $spinner.Stop() }
    Write-Host ""; Write-Host ""
    Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host ""
    if ($Raw) { return $fullResponse }
}

Set-Alias -Name cog  -Value Invoke-Cognito
Set-Alias -Name cogt -Value Invoke-CognitoTTS