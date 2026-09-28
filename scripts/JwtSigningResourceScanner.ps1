function Test-JwtSigningResourceMaterial {
    param([string]$RepositoryPath, [string[]]$TrackedFiles)

    $resourceNamePattern = '^(?:jwt(?:security|signing)?(?:key|secret|material)|token(?:security|signing)(?:key|secret|material)|(?:jwt|token)(?:key|secret))$'
    foreach ($relativePath in $TrackedFiles) {
        if ($relativePath -match '(?i)\.resx$') {
            $settings = [System.Xml.XmlReaderSettings]::new()
            $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
            $settings.XmlResolver = $null
            $settings.MaxCharactersInDocument = 8MB
            $reader = $null
            try {
                $reader = [System.Xml.XmlReader]::Create((Join-Path $RepositoryPath $relativePath), $settings)
                while ($reader.Read()) {
                    if ($reader.NodeType -ne [System.Xml.XmlNodeType]::Element -or $reader.LocalName -cne 'data') { continue }
                    $name = $reader.GetAttribute('name')
                    if ($name -notmatch $resourceNamePattern) { continue }
                    $data = $reader.ReadSubtree()
                    try {
                        while ($data.Read()) {
                            if ($data.NodeType -eq [System.Xml.XmlNodeType]::Element -and $data.LocalName -ceq 'value' -and
                                -not [string]::IsNullOrWhiteSpace($data.ReadElementContentAsString())) {
                                return $true
                            }
                        }
                    } finally { $data.Dispose() }
                }
            } catch {
                throw [System.InvalidOperationException]::new('Candidate resource XML cannot be safely inspected; details redacted.')
            } finally { if ($null -ne $reader) { $reader.Dispose() } }
        } elseif ($relativePath -match '(?i)\.Designer\.cs$') {
            try {
                $source = Get-Content -LiteralPath (Join-Path $RepositoryPath $relativePath) -Raw
            } catch {
                throw [System.InvalidOperationException]::new('Candidate generated resource cannot be safely inspected; details redacted.')
            }
            $documentation = '(?im)^\s*///\s*Looks\s+up\s+a\s+localized\s+string\s+similar\s+to\s+[^\r\n<]+\.\s*\r?\n(?:\s*///[^\r\n]*\r?\n){0,8}\s*(?:internal|public)\s+static\s+string\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{'
            foreach ($match in [regex]::Matches($source, $documentation)) {
                if ($match.Groups['name'].Value -match $resourceNamePattern) { return $true }
            }
        }
    }
    return $false
}
