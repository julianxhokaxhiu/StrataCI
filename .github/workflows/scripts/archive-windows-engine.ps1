$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$source = (Resolve-Path strata).Path
if ($env:BACKEND -eq 'metal') {
  $packages = Get-ChildItem (Join-Path $source 'out-engine-metal') -Directory
} elseif ($env:BACKEND -eq 'cuda') {
  $packages = Get-ChildItem (Join-Path $source 'out-engine') -Directory
} elseif ($env:BACKEND -eq 'hip') {
  $releaseZip = Join-Path $source 'dist/strata-windows-x64-hip.zip'
  if (-not (Test-Path $releaseZip)) {
    throw 'Windows HIP build did not produce its component input ZIP'
  }

  $stage = Join-Path $source 'stage-hip'
  Expand-Archive -Path $releaseZip -DestinationPath $stage -Force
  $version = [regex]::Match(
    (Get-Content (Join-Path $source 'CMakeLists.txt') -Raw),
    'project\([^)]*VERSION\s+([0-9.]+)'
  ).Groups[1].Value
  if (-not $version) { throw 'Could not determine the engine version from CMakeLists.txt' }

  $archs = switch ($env:VARIANT) {
    'rdna2' { @('gfx1030', 'gfx1031') }
    'rdna3' { @('gfx1100', 'gfx1101', 'gfx1102', 'gfx1151') }
    'rx9070' { @('gfx1200', 'gfx1201') }
    default { throw "Unsupported Windows HIP variant: $env:VARIANT" }
  }
  $arguments = @(
    (Join-Path $source 'packaging/package_engine.py'), '--src', $stage, '--backend', 'hip',
    '--version', $version, '--out', (Join-Path $source 'out-engine'), '--platform', $env:PLATFORM,
    '--variant', $env:VARIANT, '--build-id', $env:SOURCE_COMMIT, '--tree'
  )
  foreach ($arch in $archs) { $arguments += @('--arch', $arch) }
  python @arguments
  $packages = Get-ChildItem (Join-Path $source 'out-engine') -Directory
} else {
  throw "Unsupported engine backend: $env:BACKEND"
}

if (-not $packages) {
  throw "No engine package directory produced for $env:BACKEND $env:VARIANT"
}
$package = $packages | Select-Object -First 1
python (Join-Path $source 'packaging/package_engine.py') --verify $package.FullName

$asset = "strata-engine-$($package.Name)"
$dist = Join-Path $PWD 'dist'
New-Item -ItemType Directory -Force $dist | Out-Null
tar -czf (Join-Path $dist "$asset.tar.gz") -C $package.FullName .
