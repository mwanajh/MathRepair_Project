$ErrorActionPreference = "Stop"

$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDirectory

Write-Host "=== MathRepair Supervisor Demo ===" -ForegroundColor Cyan
Write-Host "Project: $projectDirectory"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found on PATH. Install Python or open a new terminal."
}

Write-Host "[1/6] Running model-to-verifier mock pipeline..." -ForegroundColor Yellow
python model_pipeline.py --provider mock
if ($LASTEXITCODE -ne 0) { throw "Mock pipeline failed." }

Write-Host ""
Write-Host "[2/6] Reading completed five-seed stress evaluation..." -ForegroundColor Yellow
python run_repeated_experiments.py --aggregate-only
if ($LASTEXITCODE -ne 0) { throw "Stress aggregation failed." }

Write-Host ""
Write-Host "[3/6] Reading completed held-out evaluation..." -ForegroundColor Yellow
python run_repeated_experiments.py --aggregate-only `
    --problems heldout_model_problems.csv `
    --seeds 100500 120500 140500 `
    --samples-per-problem 1
if ($LASTEXITCODE -ne 0) { throw "Held-out aggregation failed." }

Write-Host ""
Write-Host "[4/6] Building category-level research tables..." -ForegroundColor Yellow
python category_analysis.py
if ($LASTEXITCODE -ne 0) { throw "Stress category analysis failed." }
python category_analysis.py --input-dir heldout_model_problems_repeated_experiments
if ($LASTEXITCODE -ne 0) { throw "Held-out category analysis failed." }

Write-Host ""
Write-Host "[5/6] Reading expanded 36-problem evaluation..." -ForegroundColor Yellow
python run_repeated_experiments.py --aggregate-only `
    --problems expanded_heldout_model_problems.csv `
    --seeds 160500 180500 200500 `
    --samples-per-problem 1
if ($LASTEXITCODE -ne 0) { throw "Expanded aggregation failed." }
python category_analysis.py --input-dir expanded_heldout_model_problems_repeated_experiments
if ($LASTEXITCODE -ne 0) { throw "Expanded category analysis failed." }
python error_analysis.py --input-dir expanded_heldout_model_problems_repeated_experiments
if ($LASTEXITCODE -ne 0) { throw "Expanded error analysis failed." }

Write-Host ""
Write-Host "[6/6] Building adaptive allocation report..." -ForegroundColor Yellow
python allocation_report.py
if ($LASTEXITCODE -ne 0) { throw "Allocation report failed." }

Write-Host ""
Write-Host "Reports to open:" -ForegroundColor Green
Write-Host "  stress:  $projectDirectory\repeated_experiments\aggregate_report.md"
Write-Host "  held-out: $projectDirectory\heldout_model_problems_repeated_experiments\aggregate_report.md"
Write-Host "  stress categories: $projectDirectory\repeated_experiments\category_report.md"
Write-Host "  held-out categories: $projectDirectory\heldout_model_problems_repeated_experiments\category_report.md"
Write-Host "  expanded: $projectDirectory\expanded_heldout_model_problems_repeated_experiments\aggregate_report.md"
Write-Host "  expanded categories: $projectDirectory\expanded_heldout_model_problems_repeated_experiments\category_report.md"
Write-Host "  expanded errors: $projectDirectory\expanded_heldout_model_problems_repeated_experiments\error_report.md"
Write-Host "  allocation: $projectDirectory\allocation_report.md"
Write-Host "  guide:   $projectDirectory\SUPERVISOR_DEMO.docx"
Write-Host ""
Write-Host "Demo complete. Do not run the full repeated experiment during the presentation." -ForegroundColor Green
