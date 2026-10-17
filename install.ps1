# Instalador do Personal Gamification Tracker (Windows 10 / 11), chamado por Instalar.bat e Desinstalar.bat.
#
# O que ele faz (sem precisar de administrador):
#   1. Usa o Python 3.10+ que já existir no PC; se não houver, baixa o Python oficial (python.org) e instala
#      só para o seu usuário.
#   2. Copia o programa para %LOCALAPPDATA%\Programs\DailyPersonalGamification.
#   3. Cria um ambiente próprio (.venv) e instala as bibliotecas do requirements.txt.
#   4. Cria atalhos na Área de Trabalho e no Menu Iniciar e abre o programa.
# Seus dados ficam em %APPDATA%\Daily_Personal_Gamification e nunca são apagados por uma reinstalação.
param(
    [switch]$Uninstall,
    # for testing / advanced use only:
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\DailyPersonalGamification'),
    [switch]$NoShortcuts,   # don't create or remove shortcuts
    [switch]$NoLaunch,      # don't open the program at the end
    [switch]$Unattended     # never wait for Enter; uninstall keeps your data
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'   # downloads are much faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$AppName    = 'Personal Gamification Tracker'
$DataDir    = Join-Path $env:APPDATA 'Daily_Personal_Gamification'
$Source     = $PSScriptRoot
$PyVersion  = '3.12.10'
$PyUrl      = "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-amd64.exe"
$DesktopLnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk"
$MenuDir    = Join-Path ([Environment]::GetFolderPath('Programs')) $AppName
$StartupLnk = Join-Path ([Environment]::GetFolderPath('Startup')) "$AppName.lnk"

function Step($msg) { Write-Host ''; Write-Host "==> $msg" -ForegroundColor Cyan }
function Done($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Pause-End {
    if (-not $Unattended) { Write-Host ''; Read-Host 'Aperte Enter para fechar' | Out-Null }
}
function Fail($msg) {
    Write-Host ''
    Write-Host "ERRO: $msg" -ForegroundColor Red
    Pause-End
    exit 1
}

function Get-Python {
    # Returns the path of a usable python.exe (3.10 or newer), or $null.
    foreach ($try in @(@('py', '-3'), @('python'))) {
        try {
            $exe = $try[0]
            $pre = @($try | Select-Object -Skip 1)
            $out = & $exe @pre -c "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2 -and [version]$out[1].Trim() -ge [version]'3.10') {
                return $out[0].Trim()
            }
        } catch { }
    }
    $default = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path $default) { return $default }
    return $null
}

function Stop-App {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$InstallDir*" } |
        ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }
}

function New-Shortcut($path, $target, $arguments, $workDir, $icon, $description) {
    $shell = New-Object -ComObject WScript.Shell
    $s = $shell.CreateShortcut($path)
    $s.TargetPath = $target
    $s.Arguments = $arguments
    $s.WorkingDirectory = $workDir
    if ($icon) { $s.IconLocation = "$icon,0" }
    $s.Description = $description
    $s.Save()
}

# ====================================================================== uninstall
if ($Uninstall) {
    Write-Host "Desinstalar o $AppName" -ForegroundColor Cyan
    Write-Host ''
    $answer = if ($Unattended) { 'S' } else { Read-Host 'Remover o programa deste computador? (S/N)' }
    if ($answer -notmatch '^[sSyY]') { exit 0 }
    $wipe = if ($Unattended) { '' } else { Read-Host 'Apagar TAMBÉM seus dados (hábitos, diário, documentos, backups)? Digite APAGAR para apagar, ou só Enter para manter' }

    Step 'Fechando o programa'
    Stop-App
    Start-Sleep -Seconds 2

    $venvPy = Join-Path $InstallDir '.venv\Scripts\python.exe'
    if ($wipe -ceq 'APAGAR') {
        Step 'Apagando seus dados e as chaves salvas no Windows'
        if (Test-Path $venvPy) {
            & $venvPy -c "import keyring`nfor a in ('gemini-api-key','telegram-bot-token','documents-key'):`n  try: keyring.delete_password('DailyPersonalGamification', a)`n  except Exception: pass" 2>$null
        }
        Remove-Item -LiteralPath $DataDir -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Done "Seus dados continuam em $DataDir (uma nova instalação os encontra)."
    }

    Step 'Removendo atalhos e arquivos do programa'
    if (-not $NoShortcuts) {
        Remove-Item -LiteralPath $DesktopLnk, $StartupLnk -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $MenuDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Set-Location $env:TEMP
    Get-ChildItem -LiteralPath $InstallDir -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    # the folder itself may still be open in the window that started this; remove it a moment later
    Start-Process cmd.exe -ArgumentList "/c timeout /t 3 >nul & rd /s /q `"$InstallDir`"" -WindowStyle Hidden

    Write-Host ''
    Write-Host 'Pronto, o programa foi removido.' -ForegroundColor Green
    Pause-End
    exit 0
}

# ====================================================================== install
Write-Host "Instalador do $AppName" -ForegroundColor Cyan
Write-Host 'Isto leva alguns minutos e precisa de internet. Pode deixar esta janela aberta.'

if (-not (Test-Path (Join-Path $Source 'main.py'))) {
    Fail ("Os arquivos do programa não estão ao lado do instalador.`n" +
          "Primeiro extraia o ZIP: clique com o botão direito no arquivo .zip > 'Extrair tudo...',`n" +
          "depois abra a pasta extraída e dê dois cliques em Instalar.bat.")
}

# 1. Python ------------------------------------------------------------
Step 'Procurando o Python'
$python = Get-Python
if ($python) {
    Done "Encontrado: $python"
} else {
    Step "Baixando o Python $PyVersion (python.org, cerca de 27 MB)"
    $setup = Join-Path $env:TEMP "python-$PyVersion-amd64.exe"
    try {
        Invoke-WebRequest -Uri $PyUrl -OutFile $setup -UseBasicParsing
    } catch {
        Fail "Não consegui baixar o Python. Verifique a internet e rode o instalador de novo.`n$($_.Exception.Message)"
    }
    Step 'Instalando o Python (só para o seu usuário, sem pedir administrador)'
    $proc = Start-Process -FilePath $setup -Wait -PassThru -ArgumentList @(
        '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0', 'Include_launcher=1',
        'InstallLauncherAllUsers=0', 'Shortcuts=0')
    Remove-Item -LiteralPath $setup -Force -ErrorAction SilentlyContinue
    $python = Get-Python
    if ($proc.ExitCode -ne 0 -or -not $python) {
        Fail "A instalação do Python não terminou (código $($proc.ExitCode)). Tente de novo ou instale o Python 3.12 em python.org."
    }
    Done "Python instalado: $python"
}

# 2. Program files -----------------------------------------------------
Step "Copiando o programa para $InstallDir"
Stop-App
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
if ((Resolve-Path $Source).Path.TrimEnd('\') -ne (Resolve-Path $InstallDir).Path.TrimEnd('\')) {
    robocopy $Source $InstallDir /E /XD .venv .git __pycache__ /XF *.pyc .installed_version /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail 'Não consegui copiar os arquivos do programa.' }
}
Get-ChildItem -LiteralPath $InstallDir -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
Done 'Arquivos copiados.'

# 3. Libraries ---------------------------------------------------------
$venvDir = Join-Path $InstallDir '.venv'
$venvPy  = Join-Path $venvDir 'Scripts\python.exe'
$venvPyw = Join-Path $venvDir 'Scripts\pythonw.exe'
if (-not (Test-Path $venvPy)) {
    Step 'Criando o ambiente do programa'
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) { Fail 'Não consegui criar o ambiente do Python (.venv).' }
}
Step 'Instalando as bibliotecas (a primeira vez demora mais)'
& $venvPy -m pip install --disable-pip-version-check -r (Join-Path $InstallDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Fail 'Não consegui instalar as bibliotecas. Verifique a internet e rode o instalador de novo (ele continua de onde parou).'
}
Done 'Bibliotecas instaladas.'

# 4. Shortcuts + start -------------------------------------------------
$main = Join-Path $InstallDir 'main.py'
$icon = Join-Path $InstallDir 'assets\icon.ico'
if (-not $NoShortcuts) {
    Step 'Criando os atalhos'
    New-Shortcut $DesktopLnk $venvPyw "`"$main`"" $InstallDir $icon $AppName
    New-Item -ItemType Directory -Force -Path $MenuDir | Out-Null
    New-Shortcut (Join-Path $MenuDir "$AppName.lnk") $venvPyw "`"$main`"" $InstallDir $icon $AppName
    New-Shortcut (Join-Path $MenuDir "Desinstalar.lnk") (Join-Path $InstallDir 'Desinstalar.bat') '' $InstallDir $icon "Desinstalar o $AppName"
    Done 'Atalho criado na Área de Trabalho e no Menu Iniciar.'
}

if (-not $NoLaunch) {
    Step 'Abrindo o programa'
    Start-Process -FilePath $venvPyw -ArgumentList "`"$main`"" -WorkingDirectory $InstallDir
}

Write-Host ''
Write-Host 'Instalação concluída!' -ForegroundColor Green
Write-Host "Da próxima vez, abra pelo atalho '$AppName' na Área de Trabalho."
Write-Host 'O programa se atualiza sozinho quando houver versão nova (com internet).'
Write-Host 'Você já pode apagar o ZIP e a pasta extraída.'
Pause-End
