@echo off
setlocal enabledelayedexpansion

set BASE_URL=http://rails-i11zge2c4lemo09tzmnf4ggx.76.13.164.152.sslip.io
set TOKEN=jtA9abmpgCbLxGE4mMZKBaY9
set ACCOUNT_ID=1
set INBOX_ID=3

:menu
echo.
echo ============================================
echo   CHATWOOT - TESTES
echo ============================================
echo  1. Nova conversa (numero novo)
echo  2. Enviar mensagem em conversa existente
echo  3. Adicionar label em conversa
echo  4. Nota privada em conversa
echo  5. Resolver conversa
echo  6. Reabrir conversa
echo  7. Listar conversas abertas
echo  0. Sair
echo ============================================
echo.
set /p opcao="Escolha uma opcao: "

if "%opcao%"=="1" goto nova_conversa
if "%opcao%"=="2" goto enviar_mensagem
if "%opcao%"=="3" goto add_label
if "%opcao%"=="4" goto nota_privada
if "%opcao%"=="5" goto resolver
if "%opcao%"=="6" goto reabrir
if "%opcao%"=="7" goto listar
if "%opcao%"=="0" goto sair
echo Opcao invalida.
goto menu

:nova_conversa
echo.
echo --- Nova Conversa ---
set /p nome="Nome do contato: "
set /p telefone="Telefone sem + (ex: 5521999990000): "
set /p mensagem="Mensagem inicial: "
echo {"name":"%nome%","phone_number":"+%telefone%"} > %TEMP%\cw_body.json
curl -s -X POST -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/contacts" > %TEMP%\cw_resp.json
for /f %%i in ('python3 -c "import json; d=json.load(open(r\"%TEMP%\cw_resp.json\")); print(d.get(\"payload\",{}).get(\"contact\",{}).get(\"id\",\"erro\"))"') do set CONTACT_ID=%%i
echo Contato ID: %CONTACT_ID%
echo {"inbox_id":%INBOX_ID%,"contact_id":%CONTACT_ID%,"message":{"content":"%mensagem%"}} > %TEMP%\cw_body.json
curl -s -X POST -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations" > %TEMP%\cw_resp.json
for /f %%i in ('python3 -c "import json; print(json.load(open(r\"%TEMP%\cw_resp.json\")).get(\"id\",\"erro\"))"') do set CONV_ID=%%i
echo Conversa criada! ID: %CONV_ID%
pause
goto menu

:enviar_mensagem
echo.
echo --- Enviar Mensagem ---
set /p CONV_ID="ID da conversa: "
set /p mensagem="Mensagem: "
echo {"content":"%mensagem%","message_type":"outgoing","private":false} > %TEMP%\cw_body.json
curl -s -X POST -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations/%CONV_ID%/messages" > nul
echo Mensagem enviada!
pause
goto menu

:add_label
echo.
echo --- Adicionar Label ---
set /p CONV_ID="ID da conversa: "
set /p label="Label (ex: pedido_criado): "
echo {"labels":["%label%"]} > %TEMP%\cw_body.json
curl -s -X POST -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations/%CONV_ID%/labels" > nul
echo Label adicionado!
pause
goto menu

:nota_privada
echo.
echo --- Nota Privada ---
set /p CONV_ID="ID da conversa: "
set /p nota="Conteudo da nota: "
echo {"content":"%nota%","message_type":"outgoing","private":true} > %TEMP%\cw_body.json
curl -s -X POST -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations/%CONV_ID%/messages" > nul
echo Nota privada adicionada!
pause
goto menu

:resolver
echo.
echo --- Resolver Conversa ---
set /p CONV_ID="ID da conversa: "
echo {"status":"resolved"} > %TEMP%\cw_body.json
curl -s -X PATCH -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations/%CONV_ID%/toggle_status" > nul
echo Conversa resolvida!
pause
goto menu

:reabrir
echo.
echo --- Reabrir Conversa ---
set /p CONV_ID="ID da conversa: "
echo {"status":"open"} > %TEMP%\cw_body.json
curl -s -X PATCH -H "api_access_token: %TOKEN%" -H "Content-Type: application/json" -d @%TEMP%\cw_body.json "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations/%CONV_ID%/toggle_status" > nul
echo Conversa reaberta!
pause
goto menu

:listar
echo.
echo --- Conversas Abertas ---
curl -s -H "api_access_token: %TOKEN%" "%BASE_URL%/api/v1/accounts/%ACCOUNT_ID%/conversations?status=open&page=1" > %TEMP%\cw_resp.json
python3 -c "import json; d=json.load(open(r'%TEMP%\cw_resp.json')); convs=d.get('data',{}).get('payload',[]); print('Total:',len(convs)); [print('  ID:',c['id'],'|',c.get('meta',{}).get('sender',{}).get('name','?')) for c in convs[:10]]"
pause
goto menu

:sair
echo Saindo...
endlocal
exit /b 0
