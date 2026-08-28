#Requires -Version 5.1
<#
.SYNOPSIS
    Configura automaticamente a integração n8n com o Agente Revisor de PRs

.DESCRIPTION
    Este script configura:
    1. Variáveis de ambiente
    2. Testa a conexão com o GitHub
    3. Inicia o servidor HTTP (opcional)
    4. Valida a configuração

.EXAMPLE
    .\configurar.ps1
    .\configurar.ps1 -Port 8080
    .\configurar.ps1 -Server
#>

param(
    [Parameter(Mandatory=$false)]
    [int]$Port = 8080,
    
    [Parameter(Mandatory=$false)]
    [switch]$Server,
    
    [Parameter(Mandatory=$false)]
    [switch]$Test
)

# Cores para output
$Green = "`e[32m"
$Yellow = "`e[33m"
$Red = "`e[31m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Status)
    
    switch ($Status) {
        "ok" { Write-Host "$Green ✓ $Message$Reset" }
        "warn" { Write-Host "$Yellow ⚠ $Message$Reset" }
        "error" { Write-Host "$Red ✗ $Message$Reset" }
    }
}

function Test-PythonVersion {
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.(\d+)") {
            $minorVersion = [int]$Matches[1]
            if ($minorVersion -ge 10) {
                Write-Status "Python $pythonVersion encontrado" "ok"
                return $true
            }
        }
        Write-Status "Python 3.10+ necessário" "error"
        return $false
    }
    catch {
        Write-Status "Python não encontrado no PATH" "error"
        return $false
    }
}

function Test-Dependencies {
    try {
        $result = pip list 2>&1 | Select-String "langgraph|langchain|PyGithub|python-dotenv"
        if ($result) {
            Write-Status "Dependências instaladas" "ok"
            return $true
        }
        else {
            Write-Status "Dependências não instaladas. Execute: pip install -r requirements.txt" "warn"
            return $false
        }
    }
    catch {
        Write-Status "Erro ao verificar dependências" "error"
        return $false
    }
}

function Test-EnvironmentVariables {
    $envFile = Join-Path $PSScriptRoot "..\.env"
    
    if (Test-Path $envFile) {
        Write-Status "Arquivo .env encontrado" "ok"
        
        # Carrega variáveis
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^([^#][^=]+)=(.+)$") {
                $name = $Matches[1].Trim()
                $value = $Matches[2].Trim()
                if ($name -and $value) {
                    [Environment]::SetEnvironmentVariable($name, $value, "Process")
                }
            }
        }
        
        # Verifica variáveis obrigatórias
        $requiredVars = @("GITHUB_TOKEN", "GOOGLE_API_KEY")
        $missingVars = @()
        
        foreach ($var in $requiredVars) {
            if (-not [Environment]::GetEnvironmentVariable($var)) {
                $missingVars += $var
            }
        }
        
        if ($missingVars.Count -eq 0) {
            Write-Status "Variáveis de ambiente configuradas" "ok"
            return $true
        }
        else {
            Write-Status "Variáveis faltando: $($missingVars -join ', ')" "warn"
            return $false
        }
    }
    else {
        Write-Status "Arquivo .env não encontrado" "warn"
        return $false
    }
}

function Test-GitHubConnection {
    $token = [Environment]::GetEnvironmentVariable("GITHUB_TOKEN")
    
    if (-not $token) {
        Write-Status "GITHUB_TOKEN não configurado" "warn"
        return $false
    }
    
    try {
        $headers = @{
            "Authorization" = "Bearer $token"
            "Accept" = "application/vnd.github.v3+json"
        }
        
        $response = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -Method Get
        
        Write-Status "Conexão com GitHub OK (Usuário: $($response.login))" "ok"
        return $true
    }
    catch {
        Write-Status "Erro ao conectar com GitHub: $($_.Exception.Message)" "error"
        return $false
    }
}

function Start-AgentServer {
    param([int]$Port)
    
    Write-Host "`nIniciando servidor HTTP na porta $Port..."
    Write-Host "Webhook URL: http://localhost:$Port/webhook"
    Write-Host "Health check: http://localhost:$Port/health"
    Write-Host "Pressione Ctrl+C para parar`n"
    
    $adapterPath = Join-Path $PSScriptRoot "agent_adapter.py"
    
    if (Test-Path $adapterPath) {
        python $adapterPath --server --port $Port
    }
    else {
        Write-Status "agent_adapter.py não encontrado" "error"
    }
}

function Test-Integration {
    param([int]$Port)
    
    Write-Host "`nTestando integração..."
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$Port/health" -Method Get -TimeoutSec 5
        
        if ($response.status -eq "healthy") {
            Write-Status "Servidor respondendo corretamente" "ok"
            return $true
        }
        else {
            Write-Status "Servidor retornou status: $($response.status)" "warn"
            return $false
        }
    }
    catch {
        Write-Status "Servidor não está rodando. Inicie com: .\configurar.ps1 -Server" "warn"
        return $false
    }
}

# Main
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Configuração n8n - Agente Revisor PRs" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$allOk = $true

# 1. Verifica Python
Write-Host "1. Verificando Python..."
if (-not (Test-PythonVersion)) {
    $allOk = $false
}

# 2. Verifica dependências
Write-Host "`n2. Verificando dependências..."
if (-not (Test-Dependencies)) {
    $allOk = $false
}

# 3. Verifica variáveis de ambiente
Write-Host "`n3. Verificando variáveis de ambiente..."
if (-not (Test-EnvironmentVariables)) {
    $allOk = $false
}

# 4. Testa conexão GitHub
Write-Host "`n4. Testando conexão GitHub..."
if (-not (Test-GitHubConnection)) {
    $allOk = $false
}

# Resumo
Write-Host "`n========================================" -ForegroundColor Cyan
if ($allOk) {
    Write-Host "  ✓ Configuração concluída com sucesso!" -ForegroundColor Green
    Write-Host "`nPróximos passos:" -ForegroundColor Yellow
    Write-Host "  1. Importe o workflow no n8n: n8n/workflow_pr_review.json"
    Write-Host "  2. Configure a credencial GitHub Token no n8n"
    Write-Host "  3. Configure o webhook no GitHub"
    Write-Host "  4. Teste a integração"
}
else {
    Write-Host "  ⚠ Configuração incompleta" -ForegroundColor Yellow
    Write-Host "`nCorrija os problemas acima e execute novamente" -ForegroundColor Yellow
}
Write-Host "========================================`n" -ForegroundColor Cyan

# Ações baseadas em parâmetros
if ($Server) {
    Start-AgentServer -Port $Port
}

if ($Test) {
    Test-Integration -Port $Port
}