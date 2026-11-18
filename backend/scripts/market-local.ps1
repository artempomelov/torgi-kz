# Сбор цен с krisha.kz на этом компьютере и выкладка сводки в релиз «data» — то же, что делает market.yml.
# С 18.11.2026 Крыша отвечает серверам GitHub 403, и еженедельный сбор на GitHub оставляет прошлую сводку
# (письмо приходит, когда ей больше двух недель). Отсюда Крыша отдаёт объявления как обычно.
#
# Запуск из папки проекта (около часа, запросы раз в 1,5 с):
#   powershell -ExecutionPolicy Bypass -File backend\scripts\market-local.ps1
# Нужны uv и gh с входом в GitHub (gh auth status). Объявления остаются во временной папке,
# в релиз уходят только сводные цены м² — как с GitHub.

$backend = Split-Path $PSScriptRoot -Parent
$work = Join-Path $env:TEMP "torgi-market"
New-Item -ItemType Directory -Force $work -ErrorAction Stop | Out-Null
$db = Join-Path $work "market-run.db"
$index = Join-Path $work "market-index.json"
$prev = Join-Path $work "prev-market-index.json"
# каждый запуск — с чистой базы, как на GitHub: в сводку попадают только объявления, что сейчас на Крыше
Remove-Item $db, $index, $prev -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
$env:UV_LINK_MODE = "copy"

function Stop-Run([string]$message) {
    Write-Output "ОШИБКА: $message"
    Pop-Location
    exit 1
}

Push-Location $backend
uv run python -m torgi.cli market collect --db $db
if ($LASTEXITCODE) { Stop-Run "сбор не удался" }
gh release download data --pattern market-index.json --output $prev
if ($LASTEXITCODE) { Write-Output "прошлой сводки нет — недособранные города останутся без оценки" }
uv run python -m torgi.cli market index --db $db --out $index --prev $prev
if ($LASTEXITCODE) { Stop-Run "сводка не собралась" }
$n = uv run python -c "import json, sys; print(len(json.load(open(sys.argv[1], encoding='utf-8'))['segments']))" $index
Write-Output "сегментов: $n"
if ([int]$n -lt 200) { Stop-Run "слишком мало данных ($n сегментов) — сводку в релиз не выкладываем" }
gh release upload data $index --clobber
if ($LASTEXITCODE) { Stop-Run "не удалось выложить сводку в релиз data" }
Pop-Location
Write-Output "Готово: свежая сводка в релизе data, сайт возьмёт её при ближайшем обновлении (в :17 или :47)."
