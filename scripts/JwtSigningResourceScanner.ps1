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
        } elseif ($relativePath -match '(?i)\.xml$') {
            try {
                $path = Join-Path $RepositoryPath $relativePath
                if ((Get-Item -LiteralPath $path).Length -gt 8MB) {
                    throw [System.InvalidOperationException]::new('Candidate generated resource XML is too large.')
                }
                $source = Get-Content -LiteralPath $path -Raw
                $memberExpression = [regex]::new('(?is)<member\b[^>]*\bname\s*=\s*["''](?<member>[^"'']+)["''][^>]*>(?<body>.*?)</member\s*>',
                    [System.Text.RegularExpressions.RegexOptions]::None, [timespan]::FromSeconds(2))
                $summaryExpression = [regex]::new('(?is)<summary\b[^>]*>.*?Looks\s+up\s+a\s+localized\s+string\s+similar\s+to\s+\S+.*?</summary\s*>',
                    [System.Text.RegularExpressions.RegexOptions]::None, [timespan]::FromSeconds(2))
                foreach ($member in $memberExpression.Matches($source)) {
                    $memberName = $member.Groups['member'].Value
                    $nameMatch = [regex]::Match($memberName, '([A-Za-z_][A-Za-z0-9_]*)$')
                    if (-not $nameMatch.Success -or
                        $nameMatch.Groups[1].Value -notmatch $resourceNamePattern) { continue }
                    if ($summaryExpression.IsMatch($member.Groups['body'].Value)) { return $true }
                }
            } catch {
                throw [System.InvalidOperationException]::new('Candidate generated resource XML cannot be safely inspected; details redacted.')
            }
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
