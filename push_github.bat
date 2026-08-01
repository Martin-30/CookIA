@echo off
echo ====================================
echo   SAUVEGARDE COOKIA SUR GITHUB
echo ====================================
echo.

:: Se placer dans le bon dossier
cd /d "C:\Users\marti\Downloads\Projet CookIA\CookIA"

:: Demander le message du commit
set /p message="Que veux-tu ecrire comme message de sauvegarde ? : "

:: Executer les commandes Git
echo.
echo Ajout des fichiers...
git add .

echo.
echo Creation du commit...
git commit -m "%message%"

echo.
echo Envoi vers GitHub...
git push

echo.
echo ====================================
echo   TERMINE !
echo ====================================
pause