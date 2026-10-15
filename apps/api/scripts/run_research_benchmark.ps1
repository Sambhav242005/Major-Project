param(
    [ValidateSet('validate','generate','development','test')]
    [string]$Action = 'validate',
    [string]$Dataset = '',
    [string]$Model = 'qwen2.5:7b',
    [string]$PythonExecutable = 'python'
)
$ErrorActionPreference = 'Stop'
$researchScript = Join-Path $PSScriptRoot 'research_benchmark.py'
if (-not $Dataset) {
    $researchRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
    $Dataset = Join-Path $researchRoot 'output/research_benchmark/akgb_synthetic_v1'
}
function Invoke-ResearchPython {
    param([string[]]$ResearchArguments)
    & $PythonExecutable $researchScript @ResearchArguments
    if ($LASTEXITCODE -ne 0) { throw "Research command failed with exit code $LASTEXITCODE" }
}
if ($Action -eq 'validate') {
    Invoke-ResearchPython @('validate','--dataset',$Dataset)
    exit
}
if ($Action -eq 'generate') {
    # The existing release was generated with this fixed prose model.
    Invoke-ResearchPython @('generate','--output',$Dataset,'--mode','ollama','--model','qwen2.5:1.5b')
    exit
}
if ($Action -eq 'test') {
    $researchReview = Import-Csv -LiteralPath (Join-Path $Dataset 'private/human_review.csv')
    if ($researchReview.Count -ne 24 -or @($researchReview | Where-Object { $_.decision -ne 'accepted' -or -not $_.reviewer -or $_.source_and_gold_checked -ne 'yes' -or $_.unexpected_prose_claims -ne 'no' }).Count -gt 0) {
        throw 'Complete independent family review before the final test run: accepted, reviewer name, source_and_gold_checked=yes, unexpected_prose_claims=no. Use development for diagnostics now.'
    }
}
$researchSplit = if ($Action -eq 'development') { 'dev' } else { 'test' }
$researchRunDir = Join-Path (Split-Path -Parent $Dataset) 'runs'
New-Item -ItemType Directory -Path $researchRunDir -Force | Out-Null
$researchModelFile = $Model -replace '[^a-zA-Z0-9_.-]', '_'
$researchResponses = Join-Path $researchRunDir ($researchSplit + '_bm25_' + $researchModelFile + '.jsonl')
$researchSummary = Join-Path $researchRunDir ($researchSplit + '_bm25_' + $researchModelFile + '_summary.json')
Invoke-ResearchPython @('baseline','--dataset',$Dataset,'--output',$researchResponses,'--split',$researchSplit,'--model',$Model)
Invoke-ResearchPython @('score','--dataset',$Dataset,'--responses',$researchResponses,'--output',$researchSummary,'--split',$researchSplit)
Write-Host 'This is standalone BM25/Ollama evaluation. It is not the AKGB vector/graph comparison.'
