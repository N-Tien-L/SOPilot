param(
    [string]$MavenPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# Prefer installed Maven; the existing Windows wrapper can fail on a non-junction .m2.
if (-not $MavenPath) {
    $installedMaven = Get-Command mvn -ErrorAction SilentlyContinue
    if ($installedMaven) {
        $MavenPath = $installedMaven.Source
    } else {
        $wrapperCache = Join-Path $env:USERPROFILE '.m2/wrapper/dists/apache-maven-3.9.12'
        if (Test-Path -LiteralPath $wrapperCache) {
            $MavenPath = Get-ChildItem -LiteralPath $wrapperCache -Filter mvn.cmd -Recurse |
                Select-Object -First 1 -ExpandProperty FullName
        }
    }
}
if (-not $MavenPath) {
    throw 'Maven not found. Supply -MavenPath with the installed mvn/mvn.cmd path. This runner installs nothing.'
}

Push-Location $repoRoot
try {
    foreach ($scope in @('auth-service', 'user-service')) {
        Push-Location (Join-Path $repoRoot "services/$scope")
        try {
            # Offline: use existing dependency cache and write build/test outputs only to target.
            & $MavenPath -o -B test org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath '-DincludeScope=runtime' '-Dmdep.outputFile=target/runtime-classpath.txt'
            if ($LASTEXITCODE -ne 0) { throw "Build/test prerequisite failed for $scope. Resolve missing Maven dependencies before retrying." }
        } finally { Pop-Location }
    }
    node tests/integration/google-auth-flow.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Google auth backend integration test failed. Inspect the printed scratch log path.' }
} finally { Pop-Location }
