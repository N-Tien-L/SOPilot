param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host "`n==> $Message" -ForegroundColor Cyan
    & $Action
}

function Wait-ContainerHealthy {
    param(
        [Parameter(Mandatory = $true)][string]$ContainerName,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        $runningState = docker inspect --format "{{.State.Status}}" $ContainerName 2>$null
        if (-not $runningState) {
            Start-Sleep -Seconds 2
            continue
        }

        $healthState = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" $ContainerName 2>$null

        if ($runningState -eq "running" -and ($healthState -eq "healthy" -or $healthState -eq "none")) {
            Write-Host "$ContainerName is ready (state=$runningState, health=$healthState)." -ForegroundColor Green
            return
        }

        Start-Sleep -Seconds 2
    }

    throw "Timeout waiting for $ContainerName to become ready."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Please install Docker Desktop first."
}

if (-not $Force) {
    Write-Host "This will remove Docker volume 'poliwise_postgres_data' and reinitialize the database." -ForegroundColor Yellow
    $confirmation = Read-Host "Type YES to continue"
    if ($confirmation -ne "YES") {
        Write-Host "Cancelled by user." -ForegroundColor Yellow
        exit 1
    }
}

Invoke-Step -Message "Stopping compose services" -Action {
    docker compose down --remove-orphans
}

Invoke-Step -Message "Removing postgres volume (if it exists)" -Action {
    $volumeName = "poliwise_postgres_data"
    $existingVolume = docker volume ls --format "{{.Name}}" | Where-Object { $_ -eq $volumeName }

    if ($existingVolume) {
        docker volume rm $volumeName
        Write-Host "Removed volume: $volumeName" -ForegroundColor Green
    }
    else {
        Write-Host "Volume not found, skipping removal: $volumeName" -ForegroundColor DarkYellow
    }
}

Invoke-Step -Message "Starting infrastructure services (postgres, rabbitmq, minio)" -Action {
    docker compose up -d postgres rabbitmq minio
}

Invoke-Step -Message "Waiting for infrastructure to be ready" -Action {
    Wait-ContainerHealthy -ContainerName "poliwise-postgres"
    Wait-ContainerHealthy -ContainerName "poliwise-rabbitmq"
    Wait-ContainerHealthy -ContainerName "poliwise-minio"
}

Invoke-Step -Message "Verifying schemas" -Action {
    docker compose exec -T postgres psql -U poliwise -d poliwise -c "\dn"

    $schemaCount = docker compose exec -T postgres psql -U poliwise -d poliwise -t -A -c "SELECT COUNT(*) FROM pg_namespace WHERE nspname IN ('core', 'metadata', 'knowledge', 'conversation', 'analytics');"
    $schemaCount = $schemaCount.Trim()

    if ($schemaCount -ne "5") {
        throw "Schema verification failed: expected 5 application schemas, got $schemaCount."
    }
}

Invoke-Step -Message "Verifying seed data" -Action {
    docker compose exec -T postgres psql -U poliwise -d poliwise -c "SELECT COUNT(*) AS users_count FROM core.users;"
    docker compose exec -T postgres psql -U poliwise -d poliwise -c "SELECT COUNT(*) AS categories_count FROM metadata.categories;"
}

Write-Host "`nDatabase reset and bootstrap completed successfully." -ForegroundColor Green
Write-Host "Next step: docker compose up -d auth-service user-service knowledge-service metadata-service feedback-service api-gateway frontend" -ForegroundColor Green
