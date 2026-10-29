# Laudos Técnicos com IA

Laudos elétricos (baixa e média tensão), de sistemas de incêndio e de projetos de automação, com texto técnico
redigido por IA e PDF pronto para a assinatura do engenheiro. Baseado no TCC "Plataforma digital inteligente para
geração e padronização de laudos elétricos" (Lucas Alcantara Cabral).

## Rodar no computador
    python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sua_chave                    # Windows: set ANTHROPIC_API_KEY=sua_chave
    streamlit run app.py

Testes: `pytest -q`

## Administrador
Defina `ADMIN_EMAIL` e `ADMIN_SENHA` antes da primeira execução: o app cria o administrador. Depois, apague `ADMIN_SENHA` do ambiente.
- Quem cria conta fica **pendente** e só entra depois que o administrador clicar em Autorizar (menu lateral > Administração).
- O administrador também desbloqueia contas, redefine senhas (gera uma senha temporária mostrada uma vez; o usuário é obrigado a trocá-la), desativa/reativa usuários e vê o registro de ações.
- O administrador gerencia contas, mas não lê os laudos dos usuários.
- Se o único administrador ficar bloqueado, use no servidor: `python admin_cli.py desbloquear email@exemplo.com` (ou `redefinir`, `aprovar`, `promover`).
- Bancos criados antes desta versão são migrados sozinhos e as contas antigas continuam aprovadas.

## Acessar pelo celular (Android e iOS)
O app é web e abre no navegador do celular. Publique em um servidor (veja abaixo), abra o link no Chrome/Safari
e use "Adicionar à tela inicial" para ter um ícone.

## Publicar
- Streamlit Community Cloud: suba o projeto no GitHub e cadastre `ANTHROPIC_API_KEY` em Secrets.
- Railway, Render ou VPS: comando de início `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.
- Em produção use HTTPS e um disco persistente para `laudos.db` (ou migre para PostgreSQL).

## Segurança
- Senhas com bcrypt; bloqueio de 15 min após 5 tentativas erradas.
- Todas as consultas de laudos, fotos e histórico filtram por usuário (testado em `tests/test_core.py`).
- A chave da API fica só em variável de ambiente.
- Fotos são gravadas em `LAUDOS_UPLOAD_DIR/<id-do-usuário>` e cada operação valida a posse do laudo.

## Antes de usar com clientes
Os checklists em `checklists.py` e os limites em `validacao.py` são um modelo inicial. Um engenheiro deve revisá-los,
confirmar as edições vigentes das normas e as exigências do Corpo de Bombeiros do estado.
O texto da IA é rascunho: a revisão e a assinatura do engenheiro são obrigatórias.
