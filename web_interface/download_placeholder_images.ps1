# Script to download placeholder images for the Last Oasis Manager web interface
# This will download some free placeholder images from placeholder.com

# Ensure static/img directory exists
$imgDir = "static/img"
if (-not (Test-Path $imgDir)) {
    New-Item -ItemType Directory -Path $imgDir -Force
    Write-Host "Created directory: $imgDir"
}

# Define placeholder images to download
$placeholders = @(
    @{
        name = "mod-placeholder.png"
        url = "https://via.placeholder.com/64x64.png?text=Mod"
    },
    @{
        name = "favicon.ico"
        url = "https://via.placeholder.com/32x32.ico?text=LO"
    },
    @{
        name = "logo.png"
        url = "https://via.placeholder.com/200x60.png?text=Last+Oasis+Manager"
    },
    @{
        name = "server-icon.png"
        url = "https://via.placeholder.com/64x64.png?text=Server"
    },
    @{
        name = "user-avatar.png"
        url = "https://via.placeholder.com/40x40.png?text=User"
    }
)

# Download each placeholder image
foreach ($placeholder in $placeholders) {
    $outputPath = Join-Path $imgDir $placeholder.name
    try {
        Invoke-WebRequest -Uri $placeholder.url -OutFile $outputPath
        Write-Host "Downloaded $($placeholder.name) to $outputPath"
    } catch {
        Write-Error "Failed to download $($placeholder.name): $_"
    }
}

Write-Host "Image download complete. You can replace these placeholders with actual images in production."

