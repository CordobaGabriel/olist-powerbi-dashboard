param([string]$dir = (Join-Path $PSScriptRoot "..\docs\img"))
# Enmarca las capturas del README: esquinas redondeadas (fondo transparente) y borde fino,
# para que el reporte oscuro se distinga del fondo tanto en el tema claro como en el oscuro de GitHub.
# Uso: powershell -File design/frame_screenshots.ps1   (sobre capturas sin enmarcar, recortadas al lienzo)
Add-Type -AssemblyName System.Drawing
$radius = 18; $border = [System.Drawing.Color]::FromArgb(255, 0x33, 0x42, 0x6B)
Get-ChildItem $dir -Filter *.png | ForEach-Object {
  $src = [System.Drawing.Bitmap]::FromFile($_.FullName)
  $w = $src.Width; $h = $src.Height
  $out = New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($out)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $d = 2 * $radius
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $path.AddArc(0, 0, $d, $d, 180, 90); $path.AddArc($w - $d - 1, 0, $d, $d, 270, 90)
  $path.AddArc($w - $d - 1, $h - $d - 1, $d, $d, 0, 90); $path.AddArc(0, $h - $d - 1, $d, $d, 90, 90)
  $path.CloseFigure()
  $g.SetClip($path); $g.DrawImage($src, 0, 0, $w, $h); $g.ResetClip()
  $pen = New-Object System.Drawing.Pen $border, 2
  $g.DrawPath($pen, $path)
  $src.Dispose()
  $out.Save($_.FullName, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $out.Dispose()
  "enmarcada: $($_.Name) (${w}x$h)"
}
