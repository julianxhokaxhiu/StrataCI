$ErrorActionPreference = 'Stop'

$archs = switch ($env:VARIANT) {
  'rdna2' { 'gfx1030;gfx1031' }
  'rdna3' { 'gfx1100;gfx1101;gfx1102;gfx1151' }
  'rx9070' { 'gfx1200;gfx1201' }
  default { throw "Unsupported Windows HIP variant: $env:VARIANT" }
}

"STRATA_HIP_ARCHS=$archs" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"STRATA_VISION_HIP_ARCHS=$archs" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"STRATA_NO_VISION=0" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
