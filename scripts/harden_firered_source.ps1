[CmdletBinding()]
param([switch]$CheckOnly)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceRoot = Join-Path $ProjectRoot "third_party\FireRedASR2S"

$patches = @(
    [pscustomobject]@{
        Path = "fireredasr2s\fireredasr2\asr.py"
        Upstream = "F119CD2D335B7127A4E195185D4A0992C595F42F4F121084714A06AFB0EDBC1D"
        Hardened = "7D0D734684039EA3DC2E889868B52818DC79F56259A084BF0F07C5F1D897FED8"
        Replacements = @(
            [pscustomobject]@{ Before = "import logging"; After = "import argparse`nimport logging" },
            [pscustomobject]@{
                Before = "logger = logging.getLogger(__name__)"
                After = "logger = logging.getLogger(__name__)`n`n`ndef _load_checkpoint(model_path):`n    # The pinned FireRed checkpoints contain tensors and argparse.Namespace only.`n    # Restricting the unpickler prevents arbitrary globals from executing.`n    with torch.serialization.safe_globals([argparse.Namespace]):`n        return torch.load(`n            model_path,`n            map_location=lambda storage, loc: storage,`n            weights_only=True,`n        )"
            },
            [pscustomobject]@{
                Before = 'torch.load(model_path, map_location=lambda storage, loc: storage, weights_only=False)'
                After = '_load_checkpoint(model_path)'
            }
        )
    },
    [pscustomobject]@{
        Path = "fireredasr2s\fireredvad\core\detect_model.py"
        Upstream = "B3DB6DD634ECBBA1EFC3A55B8EE0EE102AE7560B08D2E5110DE3340B865D0154"
        Hardened = "54CD33F82C5CD6041D98394729579143794BE7F5B941E30BF1B313455D8A2BD1"
        Replacements = @(
            [pscustomobject]@{ Before = "import os"; After = "import argparse`nimport os" },
            [pscustomobject]@{
                Before = "        package = torch.load(model_path,`n            map_location=lambda storage, loc: storage, weights_only=False)"
                After = "        with torch.serialization.safe_globals([argparse.Namespace]):`n            package = torch.load(`n                model_path,`n                map_location=lambda storage, loc: storage,`n                weights_only=True,`n            )"
            }
        )
    },
    [pscustomobject]@{
        Path = "fireredasr2s\fireredlid\lid.py"
        Upstream = "8F2A26C3B11C5D2143E414052C3349F913F23CC85CCB4D920C3E0812C08A3B92"
        Hardened = "83C12EB0D871A58AF9DF9CDF426A379FE480D7364330F1181BB7333C5ABC7C95"
        Replacements = @(
            [pscustomobject]@{ Before = "import os"; After = "import argparse`nimport os" },
            [pscustomobject]@{
                Before = '    package = torch.load(model_path, map_location=lambda storage, loc: storage, weights_only=False)'
                After = "    with torch.serialization.safe_globals([argparse.Namespace]):`n        package = torch.load(`n            model_path,`n            map_location=lambda storage, loc: storage,`n            weights_only=True,`n        )"
            }
        )
    },
    [pscustomobject]@{
        Path = "fireredasr2s\fireredpunc\punc.py"
        Upstream = "8B082F0CB8C8791FFB207F56DB1A548D8E753648B42C2B314F3F904D98D20CAA"
        Hardened = "5EDD775DE1F4B571574204314949E0DDC3D8269E1D57646696945B98E09AE829"
        Replacements = @(
            [pscustomobject]@{ Before = "import logging"; After = "import argparse`nimport logging" },
            [pscustomobject]@{
                Before = '    package = torch.load(model_path, map_location=lambda storage, loc: storage, weights_only=False)'
                After = "    with torch.serialization.safe_globals([argparse.Namespace]):`n        package = torch.load(`n            model_path,`n            map_location=lambda storage, loc: storage,`n            weights_only=True,`n        )"
            }
        )
    }
)

foreach ($item in $patches) {
    $path = Join-Path $SourceRoot $item.Path
    if (-not (Test-Path -LiteralPath $path)) { throw "FireRed security patch target is missing: $path" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($actual -eq $item.Hardened) { continue }
    if ($actual -ne $item.Upstream) {
        throw "FireRed source differs from the locked revision: $($item.Path)"
    }
    if ($CheckOnly) { throw "FireRed restricted-deserialization patch is missing: $($item.Path)" }

    $text = [IO.File]::ReadAllText($path, [Text.UTF8Encoding]::new($false))
    foreach ($replacement in $item.Replacements) {
        $before = [string]$replacement.Before
        $after = [string]$replacement.After
        if (-not $text.Contains($before)) {
            throw "FireRed security patch context mismatch: $($item.Path)"
        }
        $text = $text.Replace($before, $after)
    }
    [IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
    $patched = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($patched -ne $item.Hardened) {
        throw "FireRed security patch verification failed: $($item.Path)"
    }
}

Write-Host "[security] FireRed restricted deserialization is enabled."
