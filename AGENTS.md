# Instalação assistida por LLM

Este repositório é um instalador OpenClaw por projeto. Quando o usuário pedir
para instalar, conduza a instalação até a validação final, executando os comandos
no ambiente do usuário. Leia README.md antes de começar.

## Preparar e executar

1. Identifique SO, usuário e diretório atual. No Windows, execute dentro do WSL
   do usuário; no Linux/WSL não execute setup como root. Confira `id`,
   `python3 --version`, `docker compose version` e
   `docker info --format '{{.OSType}}/{{.Architecture}}'`.
2. Confirme a pasta de código e o nome do novo projeto. Mantenha o kit e o código
   em pastas separadas. Leia stack.example.json e os manifests existentes;
   preserve a stack e os lockfiles do projeto. Edite stack.json quando necessário.
3. Verifique disponibilidade das portas: painel 18889 e aplicação 3000 por padrão.
   Em conflito, escolha outra porta de host e registre a escolha no JSON.
4. Execute `python3 setup.py` em terminal interativo e acompanhe os prompts.
   Colete do usuário somente decisões e autenticações que não puder resolver.
   Integrações externas são opcionais; habilite somente as solicitadas.
5. A equipe padrão contém main, produto, arquitetura, ux, frontend, backend-ai,
   qualidade, devops e cobaia. Preserve identidades, instruções e delegação.
   Terra 6.1: arquitetura, frontend, backend-ai, qualidade e devops.
   Astra: main, produto, ux e cobaia. Cobaia é independente.
   Novas instalações precisam autenticar a própria conta com acesso aos modelos.
   Use `python3 setup.py models` se o usuário escolher modelos diferentes.
6. Aguarde os downloads, inclusive EmbeddingGemma (~330 MB), mantendo o usuário
   informado. Use sessões de processo e acompanhe a saída até o encerramento.

## Autenticação, permissões e retomada

- Siga os controles de permissão da ferramenta hospedeira. Quando um bloqueio
  impedir Docker ou rede, solicite o acesso necessário pelo mecanismo disponível.
- Se Docker funcionar no terminal do usuário mas não no processo da LLM,
  compare os grupos efetivos e a distribuição WSL. Não altere a permissão do
  socket para acesso global. Não mude UID/GID da instalação existente.
- Autenticação de modelos pertence ao usuário. Prefira o fluxo de navegador
  oferecido pelo OpenClaw; se device auth não estiver habilitado, use o navegador.
  Não publique callbacks OAuth, tokens ou arquivos de credenciais.
- Não leia credenciais para o chat. Oriente o usuário a executar
  `python3 setup.py acesso` no próprio terminal para consultar endereço e token.
  A autorização para instalar não autoriza publicar segredos em logs ou no Git.
- Em falha, diagnostique a causa e repita o setup reutilizando project.json,
  stack.json, .runtime e volumes. Não apague estado para resolver uma tentativa.
  Não faça atualizações de versão ou edite o runtime sem necessidade demonstrada.
- Não copie contas, histórico ou dados de outra instância OpenClaw. A equipe
  fornecida é um modelo portátil; suas integrações exigem configuração própria.

## Concluir

O setup deve terminar com configuração válida, modelos utilizáveis, memória
indexada e embeddings prontos para cada agente, container saudável e HTTP 200
em `/healthz` na porta do painel. Confirme `python3 setup.py status`.
Informe endereço, pasta compartilhada, como usar `acesso` e eventual pareamento
de navegador. Aprovação de dispositivo deve corresponder à solicitação do usuário.
Uma pasta de código vazia ainda precisa que a aplicação seja criada; não declare
a aplicação pronta só porque o Gateway iniciou.

Não declare validação de outro sistema operacional ou arquitetura sem executá-la.
Testes de inferência usam a conta do usuário; limite-os a uma resposta curta,
sem ferramentas nem entrega externa, quando necessários para confirmar a instalação.

## Manutenção do kit

Para alterações no instalador, execute:

```bash
python3 -m unittest -q test_setup test_stack_config
node test_feature_scripts.mjs
python3 setup.py package
```

O ZIP usa a lista explícita DISTRIBUTION_FILES em setup.py. Inclua nela os novos
arquivos necessários. Nunca versione project.json, stack.json personalizado,
.runtime, volumes, sessões ou credenciais. Valide os arquivos publicados antes
de fazer commit. O teste unitário usa chamadas externas simuladas e não substitui
uma instalação real.
