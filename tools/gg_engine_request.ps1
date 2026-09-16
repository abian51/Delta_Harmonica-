param(
    [ValidateSet('GET', 'POST', 'PUT', 'DELETE')]
    [string]$Method,
    [string]$Path,
    [string]$CorePropsPath = 'C:\ProgramData\SteelSeries\GG\coreProps.json'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

try {
    $props = Get-Content -LiteralPath $CorePropsPath -Raw | ConvertFrom-Json
    if (-not $props.encryptedAddress) {
        throw 'GG coreProps.json does not contain encryptedAddress.'
    }

    $now = Get-Date
    $store = [System.Security.Cryptography.X509Certificates.X509Store]::new(
        [System.Security.Cryptography.X509Certificates.StoreName]::My,
        [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine
    )
    $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
    $certificate = $store.Certificates |
        Where-Object {
            $_.Subject -eq 'CN=SteelSeries A/S' -and
            $_.HasPrivateKey -and
            $_.NotBefore -le $now -and
            $_.NotAfter -gt $now
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
    if (-not $certificate) {
        throw 'No usable SteelSeries local certificate was found.'
    }

    $handler = [System.Net.Http.HttpClientHandler]::new()
    [void]$handler.ClientCertificates.Add($certificate)
    # The endpoint is restricted to loopback and also requires GG's client certificate.
    $handler.ServerCertificateCustomValidationCallback =
        [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
    $client = [System.Net.Http.HttpClient]::new($handler)
    $uri = "https://$($props.encryptedAddress)/$($Path.TrimStart('/'))"
    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::new($Method),
        $uri
    )
    if ($Method -notin @('GET', 'HEAD')) {
        $body = [Console]::In.ReadToEnd()
        if ([string]::IsNullOrWhiteSpace($body)) { $body = '{}' }
        $request.Content = [System.Net.Http.ByteArrayContent]::new(
            [System.Text.Encoding]::UTF8.GetBytes($body)
        )
        # Engine 119 rejects "application/json; charset=utf-8" even though it is valid.
        # Match the browser frontend's exact header value.
        $request.Content.Headers.ContentType =
            [System.Net.Http.Headers.MediaTypeHeaderValue]::new('application/json')
    }

    $response = $client.SendAsync($request).GetAwaiter().GetResult()
    $responseBytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
    [ordered]@{
        ok = $response.IsSuccessStatusCode
        status = [int]$response.StatusCode
        reason = $response.ReasonPhrase
        bodyBase64 = [System.Convert]::ToBase64String($responseBytes)
    } | ConvertTo-Json -Compress
    if (-not $response.IsSuccessStatusCode) { exit 2 }
}
catch {
    [ordered]@{
        ok = $false
        status = 0
        reason = $_.Exception.Message
        bodyBase64 = ''
    } | ConvertTo-Json -Compress
    exit 1
}
finally {
    if ($request) { $request.Dispose() }
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
    if ($store) { $store.Dispose() }
}
