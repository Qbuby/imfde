# 注册每日 0 点本地计划任务（数据抓取 + 报告预生成 + push 部署）
# 用法：以管理员身份运行一次  powershell -File scripts\register_daily_task.ps1

$taskName = "imfde-daily-update"
$bat = "D:\program\imfde\scripts\daily_local.bat"

# 每天北京时间 0:00 触发
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`""
$trigger = New-ScheduledTaskTrigger -Daily -At "00:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "计划任务 '$taskName' 已注册：每天 00:00 运行 $bat"
