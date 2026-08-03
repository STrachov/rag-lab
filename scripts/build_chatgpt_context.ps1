[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$outputPath = Join-Path $repoRoot "temp_docs\RAG_LAB_CHATGPT_CONTEXT.md"
$sourceFiles = @(
    "docs/CURRENT_STATE.md"
    "AGENTS.md"
    "README.md"
    "docs/PRODUCT_SPEC.md"
    "docs/ARCHITECTURE.md"
    "docs/DOMAIN_MODEL.md"
    "docs/API_CONTRACTS.md"
    "docs/DEVELOPMENT_WORKFLOW.md"
    "docs/DATA_POLICY.md"
    "docs/DECISIONS.md"
)

$missingFiles = @(
    $sourceFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $repoRoot $_) -PathType Leaf)
    }
)
if ($missingFiles.Count -gt 0) {
    throw "Cannot build ChatGPT context bundle. Missing source files: $($missingFiles -join ', ')"
}

$commit = "unknown"
try {
    $candidate = & git -C $repoRoot rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $candidate) {
        $commit = (($candidate -join "").Trim())
    }
}
catch {
    # Git metadata is useful but not required to build the documentation bundle.
}

$builder = [System.Text.StringBuilder]::new()
[void]$builder.AppendLine("# RAG Lab ChatGPT Context Bundle")
[void]$builder.AppendLine()
[void]$builder.AppendLine("Generated from explicit repository documentation sources.")
[void]$builder.AppendLine()
[void]$builder.AppendLine("- Generated at (UTC): $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))")
[void]$builder.AppendLine("- Git commit: ``$commit``")
[void]$builder.AppendLine("- Output is generated: edit the source files, not this bundle.")
[void]$builder.AppendLine()
[void]$builder.AppendLine("## Instructions For ChatGPT")
[void]$builder.AppendLine()
[void]$builder.AppendLine("- Use ``docs/CURRENT_STATE.md`` as the source of truth for implemented behavior.")
[void]$builder.AppendLine("- Use ``docs/PRODUCT_SPEC.md`` for target behavior and roadmap.")
[void]$builder.AppendLine("- Use ``docs/API_CONTRACTS.md`` for the current external API.")
[void]$builder.AppendLine("- Use ``docs/DOMAIN_MODEL.md`` for entity semantics.")
[void]$builder.AppendLine("- Use ``AGENTS.md`` for architectural constraints and repository terminology.")
[void]$builder.AppendLine("- When documents conflict, distinguish current implementation from target design.")
[void]$builder.AppendLine("- Do not describe planned, reserved, or placeholder features as implemented.")
[void]$builder.AppendLine("- Treat remote-provider data movement, sensitive data, and derived caches according to ``docs/DATA_POLICY.md``.")
[void]$builder.AppendLine()
[void]$builder.AppendLine("## Included Sources")
[void]$builder.AppendLine()
foreach ($relativePath in $sourceFiles) {
    [void]$builder.AppendLine("- ``$relativePath``")
}

foreach ($relativePath in $sourceFiles) {
    $sourcePath = Join-Path $repoRoot $relativePath
    $content = [System.IO.File]::ReadAllText($sourcePath)

    [void]$builder.AppendLine()
    [void]$builder.AppendLine("---")
    [void]$builder.AppendLine()
    [void]$builder.AppendLine("## Source File: ``$relativePath``")
    [void]$builder.AppendLine()
    [void]$builder.Append($content.TrimEnd())
    [void]$builder.AppendLine()
}

$outputDirectory = Split-Path -Parent $outputPath
[void][System.IO.Directory]::CreateDirectory($outputDirectory)
$bundle = $builder.ToString()
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($outputPath, $bundle, $utf8WithoutBom)

$outputFile = Get-Item -LiteralPath $outputPath
$lineCount = ([regex]::Matches($bundle, "`r`n|`r|`n").Count + 1)
$relativeOutputPath = $outputFile.FullName.Substring($repoRoot.Length).TrimStart('\', '/')

Write-Output "ChatGPT context bundle created: $relativeOutputPath"
Write-Output "Sources: $($sourceFiles.Count)"
Write-Output "Lines: $lineCount"
Write-Output "Bytes: $($outputFile.Length)"
