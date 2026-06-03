# Template for registering the Cerebras API key. Copy to set_api_key.ps1 and put your real key.
# Run (dot-source): . "<project>\set_api_key.ps1"

$KEY = "PUT_KEY_HERE"

# 1) Apply to current session
$env:CEREBRAS_API_KEY = $KEY

# 2) Persist to User scope (inherited by newly spawned processes)
[Environment]::SetEnvironmentVariable("CEREBRAS_API_KEY", $KEY, "User")

if ($KEY -eq "PUT_KEY_HERE") {
    Write-Output "[!] Key not set yet. Open the file and replace the placeholder."
} else {
    Write-Output "[OK] CEREBRAS_API_KEY set (length $($KEY.Length))."
}
