$ErrorActionPreference = 'Stop'

$archs = switch ($env:VARIANT) {
  'rdna2' { 'gfx1030;gfx1031;gfx1032' }
  'rdna3' { 'gfx1100;gfx1101;gfx1102;gfx1151' }
  'rx9070' { 'gfx1200;gfx1201' }
  'strix' { 'gfx1151' }
  default { throw "Unsupported Windows HIP variant: $env:VARIANT" }
}

if ($env:FAMILY -eq 'inkling' -and $env:VARIANT -eq 'rdna3') {
  $archs = 'gfx1100;gfx1101;gfx1102;gfx1103;gfx1150'
}

"STRATA_HIP_ARCHS=$archs" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"STRATA_VISION_HIP_ARCHS=$archs" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"STRATA_NO_VISION=0" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8

if ($env:FAMILY -eq 'inkling') {
  $PSNativeCommandUseErrorActionPreference = $true
  $venv = Join-Path (Resolve-Path strata).Path '.rocm-win'
  python -m venv $venv
  $python = Join-Path $venv 'Scripts\python.exe'
  $extras = 'libraries,devel,' + (($archs -split ';' | ForEach-Object { "device-$_" }) -join ',')
  & $python -m pip install --index-url https://nightly.repo.amd.com/rocm/whl-next/ "rocm[$extras]==10.2.0a20260930"
  & "$venv\Scripts\rocm-sdk.exe" init
  $sdk = & "$venv\Scripts\rocm-sdk.exe" path --root
  "HP=$sdk" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
}
