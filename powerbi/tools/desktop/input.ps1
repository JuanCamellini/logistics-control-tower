# Mouse clicks and keystrokes on the Power BI Desktop window (screen coordinates in physical pixels).
# Usage: input.ps1 -Click "x,y" [-Right] [-Double] | -Keys "text" | -Scroll "x,y,delta"
param([string]$Click, [switch]$Right, [switch]$Double, [switch]$Ctrl, [string]$Keys, [string]$Scroll)
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Inp {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, int data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@
[Inp]::SetProcessDPIAware() | Out-Null
$p = Get-Process PBIDesktop -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($p) { [Inp]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 300 }
# Windows refuses to switch focus while the user works in another app: never send input to that app.
if (-not $p -or [Inp]::GetForegroundWindow() -ne $p.MainWindowHandle) { "skipped: Power BI Desktop is not in the foreground"; exit 1 }
if ($Click) {
  $x, $y = $Click.Split(",") | ForEach-Object { [int]$_ }
  [Inp]::SetCursorPos($x, $y) | Out-Null; Start-Sleep -Milliseconds 150
  $down, $up = if ($Right) { 0x0008, 0x0010 } else { 0x0002, 0x0004 }
  $times = if ($Double) { 2 } else { 1 }
  if ($Ctrl) { [Inp]::keybd_event(0x11, 0x1D, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 100 }
  for ($i = 0; $i -lt $times; $i++) { [Inp]::mouse_event($down, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 60; [Inp]::mouse_event($up, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 80 }
  if ($Ctrl) { Start-Sleep -Milliseconds 100; [Inp]::keybd_event(0x11, 0x1D, 2, [UIntPtr]::Zero) }
}
if ($Scroll) {
  $x, $y, $d = $Scroll.Split(",") | ForEach-Object { [int]$_ }
  [Inp]::SetCursorPos($x, $y) | Out-Null; Start-Sleep -Milliseconds 100
  [Inp]::mouse_event(0x0800, 0, 0, $d, [UIntPtr]::Zero)
}
if ($Keys) { [System.Windows.Forms.SendKeys]::SendWait($Keys) }
"ok"
