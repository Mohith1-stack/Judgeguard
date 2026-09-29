$ErrorActionPreference = "Stop"
$report = "acceptance-report.txt"
"JudgeGuard final acceptance" | Set-Content $report
("Generated: " + [DateTime]::UtcNow.ToString("o")) | Add-Content $report

Write-Host "[1/5] Python compile"
python -m compileall -q apps/api/app
"PASS: Python compilation" | Add-Content $report

Write-Host "[2/5] Automated tests"
$env:PYTHONPATH = "."
python -m pytest -q | Tee-Object -FilePath $report -Append

Write-Host "[3/5] Docker compose config"
docker compose config | Out-Null
"PASS: docker-compose configuration" | Add-Content $report

Write-Host "[4/5] Docker stack"
docker compose up -d --build
docker compose ps | Tee-Object -FilePath $report -Append

Write-Host "[5/5] Health checks"
Invoke-WebRequest http://localhost:8000/api/v1/health -UseBasicParsing | Out-Null
Invoke-WebRequest http://localhost:8000/api/v1/health/db -UseBasicParsing | Out-Null
"PASS: API and database health" | Add-Content $report
"" | Add-Content $report
"Live acceptance still required on the target laptop:" | Add-Content $report
"- backend role isolation" | Add-Content $report
"- deadline enforcement" | Add-Content $report
"- evaluation submission ownership" | Add-Content $report
"- duplicate/rate-limited public voting" | Add-Content $report
"- organizer-readable audit log" | Add-Content $report
"- webhook signature verification" | Add-Content $report
"- public Ed25519 participation-record verification" | Add-Content $report
"- bulk export/import round trip" | Add-Content $report

Write-Host "JudgeGuard verification completed. See acceptance-report.txt"
