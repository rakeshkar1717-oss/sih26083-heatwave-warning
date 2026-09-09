@echo off
set "PATH=C:\Users\chand\AppData\Local\Programs\Git\cmd;%PATH%"
echo ======================================================================
echo   SIH26083: Pushing Project to GitHub
echo   Repository: https://github.com/rakeshkar1717-oss/sih26083-heatwave-warning
echo ======================================================================
echo.
git push -u origin main
echo.
echo ======================================================================
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Code successfully pushed to GitHub!
) else (
    echo [NOTE] If prompted for password, use a GitHub Personal Access Token (PAT).
    echo Generate one at: https://github.com/settings/tokens (check 'repo' box).
)
echo ======================================================================
pause
