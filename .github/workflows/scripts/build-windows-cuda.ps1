$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$source = (Resolve-Path strata).Path

if ($env:VARIANT -eq 'cuda12') {
  $archs = '60-real;61-real;70-real;75-real;80-real;86-real;120-real;89-real;89-virtual'
  $extra = '-DSTRATA_EXPERIMENTAL_SM60=ON'
  $archArgs = @('--arch','sm_60','--arch','sm_61','--arch','sm_70','--arch','sm_75','--arch','sm_80','--arch','sm_86','--arch','sm_120','--arch','sm_89','--arch','compute_89')
  $driver = '575.51'
} elseif ($env:VARIANT -eq 'cuda13') {
  $archs = '75-real;86-real;89-real;120-real;120-virtual'
  $extra = ''
  $archArgs = @('--arch','sm_75','--arch','sm_86','--arch','sm_89','--arch','sm_120','--arch','compute_120')
  $driver = '580.65'
} else {
  throw "Unsupported Windows CUDA variant: $env:VARIANT"
}

$cmakeArgs = @(
  '-S', "$source\engine", '-B', "$source\build-engine", '-G', 'Ninja',
  '-DCMAKE_BUILD_TYPE=Release', '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_BUILD_TESTS=OFF',
  '-DSTRATA_NATIVE_EXPERTS=ON', '-DSTRATA_PORTABLE=ON', '-DSTRATA_Q6K_EXPERTS=ON',
  "-DCMAKE_CUDA_ARCHITECTURES=$archs", "-DCUDAToolkit_ROOT=$env:CUDA_PATH"
)
if ($extra) { $cmakeArgs += $extra }
cmake @cmakeArgs
cmake --build "$source\build-engine" --target strata

$vision = "$source\build-vision"
cmake -S "$source\terminal\tools\vision" -B $vision -G Ninja -DCMAKE_BUILD_TYPE=Release `
  -DSTRATA_VISION_CUDA=ON -DSTRATA_PORTABLE=ON `
  "-DCMAKE_CUDA_ARCHITECTURES=$archs" "-DCUDAToolkit_ROOT=$env:CUDA_PATH"
cmake --build $vision --target strata-vision

$version = [regex]::Match(
  (Get-Content "$source\engine\CMakeLists.txt" -Raw),
  'project\([^)]*VERSION\s+([0-9.]+)'
).Groups[1].Value
if (-not $version) { throw 'Could not determine the engine version from CMakeLists.txt' }

$stage = "$source\stage"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item "$source\build-engine\strata.exe" $stage
Copy-Item "$vision\bin\strata-vision.exe" $stage
python "$source\tools\packaging\package_engine.py" --stamp-vision $stage `
  --vision-archs ($archs -replace '-real|-virtual','')

$arguments = @(
  "$source\tools\packaging\package_engine.py", '--src', $stage, '--backend', 'cuda',
  '--version', $version, '--out', "$source\out-engine", '--platform', 'windows-x86_64',
  '--build-id', $env:SOURCE_COMMIT, '--variant', $env:VARIANT, '--min-driver', "nvidia=$driver",
  '--search', "$env:CUDA_PATH\bin\x64", '--search', "$env:CUDA_PATH\bin"
)
$arguments += $archArgs
python @arguments
