param(
  [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Set-Location $RepoRoot
node tools/static_server.mjs $Port docs
