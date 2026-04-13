@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 2W Pneus

if /i "%1"=="agente"   goto NOVO_PADRAO
if /i "%1"=="cadastro" goto CADASTRO
if /i "%1"=="testes"   goto TESTES_UNIT
if /i "%1"=="cache"    goto LIMPAR_CACHE

:MENU_PRINCIPAL
cls
echo.
echo  ==========================================
echo    2W PNEUS - PAINEL CENTRAL
echo  ==========================================
echo.
echo  -- ATENDIMENTO --
echo   [1] Nova sessao (padrao)
echo   [2] Nova sessao com telefone
echo   [3] Retomar sessao existente
echo   [4] Modo debug
echo.
echo  -- CADASTRO --
echo   [5] Cadastrar pneus / estoque
echo.
echo  -- TESTES --
echo   [6] Testes unitarios (tests/)
echo   [7] Integrado F1-F5
echo   [8] Conversa natural (7 turnos)
echo   [9] Stress / regressions
echo   [M] Mais testes...
echo.
echo  -- UTILITARIOS --
echo   [U] Utilitarios (cache, deps, logs)
echo.
echo   [0] Sair
echo.
choice /c 0123456789MU /n /m "  Opcao: "
set OPT=%errorlevel%
if %OPT%==1  goto SAIR
if %OPT%==2  goto NOVO_PADRAO
if %OPT%==3  goto NOVO_TELEFONE
if %OPT%==4  goto RETOMAR
if %OPT%==5  goto DEBUG
if %OPT%==6  goto CADASTRO
if %OPT%==7  goto TESTES_UNIT
if %OPT%==8  goto TESTE_INTEGRADO
if %OPT%==9  goto TESTE_CONVERSA
if %OPT%==10 goto TESTE_STRESS
if %OPT%==11 goto MENU_TESTES
if %OPT%==12 goto MENU_UTILS
goto MENU_PRINCIPAL

:MENU_TESTES
cls
echo.
echo  ==========================================
echo    MAIS TESTES
echo  ==========================================
echo.
echo   [1] Multi-item / multi-moto
echo   [2] Sessao timeout
echo   [3] Inteligencia cliente
echo   [4] Imagem
echo   [5] Fase 11 (regressao completa)
echo   [6] Fases 1-2-3 (fundacao)
echo   [7] Fase 4 (tools)
echo   [8] Fase 5 (IA)
echo   [9] Fase 6 (pedido/promotor)
echo   [0] Voltar
echo.
choice /c 0123456789 /n /m "  Opcao: "
set OPT2=%errorlevel%
if %OPT2%==1  goto MENU_PRINCIPAL
if %OPT2%==2  goto TESTE_MULTI
if %OPT2%==3  goto TESTE_TIMEOUT
if %OPT2%==4  goto TESTE_INTELIGENCIA
if %OPT2%==5  goto TESTE_IMAGEM
if %OPT2%==6  goto TESTE_FASE11
if %OPT2%==7  goto TESTE_FASES123
if %OPT2%==8  goto TESTE_FASE4
if %OPT2%==9  goto TESTE_FASE5
if %OPT2%==10 goto TESTE_FASE6
goto MENU_TESTES

:MENU_UTILS
cls
echo.
echo  ==========================================
echo    UTILITARIOS
echo  ==========================================
echo.
echo   [1] Limpar cache Python
echo   [2] Verificar dependencias
echo   [3] Ver logs ao vivo
echo   [4] Verificar imports do pacote
echo   [0] Voltar
echo.
choice /c 01234 /n /m "  Opcao: "
set OPT3=%errorlevel%
if %OPT3%==1 goto MENU_PRINCIPAL
if %OPT3%==2 goto LIMPAR_CACHE
if %OPT3%==3 goto VERIFICAR_DEPS
if %OPT3%==4 goto VER_LOGS
if %OPT3%==5 goto VERIFICAR_IMPORTS
goto MENU_UTILS


:: ==========================================
:: ATENDIMENTO
:: ==========================================

:NOVO_PADRAO
cls
echo.
echo  Iniciando nova sessao (padrao)...
echo.
python -m agente_2w.main --contato 5521999999999
goto POS_SESSAO

:NOVO_TELEFONE
cls
echo.
set /p TELEFONE="  Telefone (ex: 5554999998888): "
if "%TELEFONE%"=="" (
    echo  Telefone nao pode ser vazio.
    timeout /t 2 >nul
    goto MENU_PRINCIPAL
)
python -m agente_2w.main --contato %TELEFONE%
goto POS_SESSAO

:RETOMAR
cls
echo.
set /p SESSAO_ID="  Cole o UUID da sessao: "
if "%SESSAO_ID%"=="" (
    echo  UUID nao pode ser vazio.
    timeout /t 2 >nul
    goto MENU_PRINCIPAL
)
python -m agente_2w.main --sessao %SESSAO_ID%
goto POS_SESSAO

:DEBUG
cls
echo.
set /p TELEFONE_DBG="  Telefone (Enter = padrao): "
if "%TELEFONE_DBG%"=="" set TELEFONE_DBG=5521999999999
python -m agente_2w.main --contato %TELEFONE_DBG% --debug
goto POS_SESSAO

:POS_SESSAO
echo.
echo  ------------------------------------------
echo   Sessao encerrada.
echo  ------------------------------------------
echo.
choice /c 012 /n /m "  [1] Nova sessao  [2] Menu principal  [0] Sair: "
if errorlevel 3 goto SAIR
if errorlevel 2 goto MENU_PRINCIPAL
if errorlevel 1 goto NOVO_PADRAO
goto MENU_PRINCIPAL


:: ==========================================
:: CADASTRO
:: ==========================================

:CADASTRO
cls
echo.
echo  Abrindo cadastro...
echo.
python -X utf8 cadastro.py
echo.
pause
goto MENU_PRINCIPAL


:: ==========================================
:: TESTES
:: ==========================================

:TESTES_UNIT
cls
echo.
echo  Rodando testes unitarios (tests/)...
echo.
python -X utf8 -m pytest tests/ -v 2>nul || python -X utf8 -c "import subprocess,sys,glob;[print(('OK  ' if subprocess.run([sys.executable,'-X','utf8',a],capture_output=True).returncode==0 else 'FAIL')+' '+a) for a in sorted(glob.glob('tests/test_*.py'))]"
echo.
pause
goto MENU_PRINCIPAL

:TESTE_INTEGRADO
cls
echo.
echo  Integrado F1-F5 (requer OpenAI + Supabase)...
echo.
python -X utf8 teste_integrado_f1_f5.py
echo.
pause
goto MENU_PRINCIPAL

:TESTE_CONVERSA
cls
echo.
echo  Conversa natural (7 turnos reais)...
echo.
python -X utf8 teste_conversa_natural.py
echo.
pause
goto MENU_PRINCIPAL

:TESTE_STRESS
cls
echo.
echo  Stress / regressions...
echo.
python -X utf8 teste_stress.py
echo.
pause
goto MENU_PRINCIPAL

:TESTE_MULTI
cls
echo.
echo  Multi-item / multi-moto...
echo.
python -X utf8 teste_multi_item.py
echo.
pause
goto MENU_TESTES

:TESTE_TIMEOUT
cls
echo.
echo  Sessao timeout...
echo.
python -X utf8 teste_sessao_timeout.py
echo.
pause
goto MENU_TESTES

:TESTE_INTELIGENCIA
cls
echo.
echo  Inteligencia cliente...
echo.
python -X utf8 teste_inteligencia_cliente.py
echo.
pause
goto MENU_TESTES

:TESTE_IMAGEM
cls
echo.
echo  Teste de imagem...
echo.
python -X utf8 teste_imagem.py
echo.
pause
goto MENU_TESTES

:TESTE_FASE11
cls
echo.
echo  Regressao completa (fase 11)...
echo.
python -X utf8 teste_fase11.py
echo.
pause
goto MENU_TESTES

:TESTE_FASES123
cls
echo.
echo  Fundacao fases 1-2-3...
echo.
python -X utf8 teste_fases_1_2_3.py
echo.
pause
goto MENU_TESTES

:TESTE_FASE4
cls
echo.
echo  Fase 4 (tools)...
echo.
python -X utf8 teste_fase_4.py
echo.
pause
goto MENU_TESTES

:TESTE_FASE5
cls
echo.
echo  Fase 5 (IA)...
echo.
python -X utf8 teste_fase_5.py
echo.
pause
goto MENU_TESTES

:TESTE_FASE6
cls
echo.
echo  Fase 6 (pedido/promotor)...
echo.
python -X utf8 teste_fase_6.py
echo.
pause
goto MENU_TESTES


:: ==========================================
:: UTILITARIOS
:: ==========================================

:LIMPAR_CACHE
cls
echo.
echo  Limpando cache Python...
echo.
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)
del /s /q *.pyc >nul 2>&1
echo  Pronto!
timeout /t 2 >nul
goto MENU_UTILS

:VERIFICAR_DEPS
cls
echo.
echo  Verificando dependencias...
echo.
python -c "deps=['openai','supabase','pydantic','httpx','dotenv','zoneinfo'];[print('  OK   '+d) if __import__(d.replace('-','_')) or True else print('  FAIL '+d) for d in deps]" 2>nul
python -c "import sys; print('\n  Python '+sys.version)"
echo.
pause
goto MENU_UTILS

:VER_LOGS
cls
echo.
echo  Logs ao vivo (Ctrl+C para parar)...
echo.
if exist logs\agente.log (
    powershell -Command "Get-Content 'logs\agente.log' -Wait -Tail 40"
) else (
    echo  logs\agente.log nao encontrado. Inicie o agente primeiro.
    echo.
    pause
)
goto MENU_UTILS

:VERIFICAR_IMPORTS
cls
echo.
echo  Verificando imports do pacote...
echo.
python -c "from agente_2w.engine.orquestrador import processar_turno,MENSAGEM_FALHA_SEGURA;from agente_2w.engine.promotor import promover_para_pedido;from agente_2w.ia.agente import chamar_agente;print('  Todos os modulos OK')"
echo.
pause
goto MENU_UTILS


:: ==========================================

:SAIR
echo.
echo  Ate logo!
timeout /t 1 >nul
exit
