param([int]$LocalPort = 18766, [int]$RemotePort = 28760)
# Run in a terminal and keep it open, or use Start-Process -WindowStyle Hidden.
ssh -F NUL -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -i "$env:USERPROFILE\.ssh\A6000\kxliu_ed25519" -o "CertificateFile=$env:USERPROFILE\.ssh\A6000\kxliu_ed25519-cert.pub" -L "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}" kxliu@100.111.100.200
