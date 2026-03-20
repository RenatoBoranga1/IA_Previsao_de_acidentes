param(
    [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$overviewPath = Join-Path $projectRoot "docs\screenshots\dashboard-overview.png"
$mobilePath = Join-Path $projectRoot "docs\screenshots\dashboard-mobile.png"
$indexUri = "file:///$($projectRoot.Replace('\', '/'))/index.html?demo=1&demoRole=admin"

if (-not (Test-Path $ChromePath)) {
    throw "Chrome nao encontrado em $ChromePath"
}

& $ChromePath --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --window-size=1600,2200 --screenshot=$overviewPath $indexUri
& $ChromePath --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --window-size=430,1600 --screenshot=$mobilePath $indexUri
