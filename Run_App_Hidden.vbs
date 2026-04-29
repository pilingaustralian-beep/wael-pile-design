Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c py -m streamlit run app.py", 0, False
