set protocol_path="\"%~dp0forzaprotocolselector.exe\" \"%%1\""
reg add HKCU\Software\Classes\ForzaHorizon6ProtocolSelect /f /t REG_SZ /d "URL:ForzaHorizon6ProtocolSelect"
reg add HKCU\Software\Classes\ForzaHorizon6ProtocolSelect /f /v "URL Protocol" /t REG_SZ
reg add HKCU\Software\Classes\ForzaHorizon6ProtocolSelect\shell\open\command /f /t REG_SZ /d %protocol_path%
reg add HKLM\SOFTWARE\Microsoft\XboxLive\2079757188 /f /v "AcceptProtocol" /t REG_SZ /d "ForzaHorizon6ProtocolSelect://?1;{0};{1};{2}"
reg add HKLM\SOFTWARE\Microsoft\XboxLive\2079757188 /f /v "JoinProtocol" /t REG_SZ /d "ForzaHorizon6ProtocolSelect://?2;{0};{1};{2}"
pause