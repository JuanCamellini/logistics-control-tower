# Crops a region of a screenshot: crop.ps1 -In a.png -Out b.png -Rect "x,y,w,h"
param([string]$In, [string]$Out, [string]$Rect)
Add-Type -AssemblyName System.Drawing
$x, $y, $w, $h = $Rect.Split(",") | ForEach-Object { [int]$_ }
$src = [System.Drawing.Bitmap]::FromFile($In)
$dst = $src.Clone((New-Object System.Drawing.Rectangle $x, $y, $w, $h), $src.PixelFormat)
New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
$dst.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$src.Dispose(); $dst.Dispose()
"cropped -> $Out"
