# Tunguska OpenClaw Team

Este kit cria uma instância OpenClaw com ferramentas de desenvolvimento, código montado do computador e memória local com llama.cpp + EmbeddingGemma 300M. Cada extração configurada recebe um identificador próprio de Docker Compose e volumes próprios.

## Instalar com ajuda de uma LLM

A instalação é conduzida por um assistente com LLM e acesso ao terminal local, como o Codex. O arquivo [AGENTS.md](AGENTS.md) contém o roteiro de execução, diagnóstico, retomada e validação. A pessoa informa o projeto e autentica suas próprias contas durante o processo.

Clone o repositório:

~~~bash
git clone https://github.com/gianpasqualini/tunguska-openclaw-team.git
cd tunguska-openclaw-team
~~~

Como alternativa, baixe o pacote na [página de versões](https://github.com/gianpasqualini/tunguska-openclaw-team/releases). Abra a pasta do kit na ferramenta com LLM. Use a seguinte solicitação para iniciar:

> Leia AGENTS.md e README.md e execute a instalação completa deste OpenClaw no meu computador. Verifique o Docker e o ambiente do meu usuário, configure a pasta de código que eu indicar e mantenha a equipe e os modelos padrão. Conduza os comandos e diagnósticos até validar agentes, memória e painel. Peça minha participação quando precisar autenticar uma conta ou faltar uma decisão. Ao terminar, informe como consultar o token usando python3 setup.py acesso.

A LLM precisa poder executar comandos locais e usar rede/Docker pelas permissões da ferramenta. Um chat sem terminal pode orientar, mas a execução dependerá da pessoa. No Windows, abra a pasta pela distribuição WSL do seu usuário.

O usuário escolhe seu provedor de nuvem para conversar com o agente. O setup instala o modelo de embeddings para a busca de memória e baixa aproximadamente 330 MB de pesos, além do runtime e da imagem. A execução dos embeddings usa CPU no contêiner Linux, inclusive no Mac.

## Requisitos por sistema

| Sistema | Preparação |
| --- | --- |
| Windows 11 / WSL2 | Docker Desktop com integração na distribuição Ubuntu e Python 3.10+ dentro do WSL. Execute os comandos no terminal Ubuntu. |
| Linux | Docker Engine, plugin Docker Compose v2 ou superior e Python 3.10+. Seu usuário precisa conseguir executar Docker. |
| macOS Intel ou Apple Silicon | Docker Desktop e Python 3.10+. Execute os comandos no Terminal. |

A imagem oficial tem variantes Linux AMD64 e ARM64, escolhidas automaticamente pelo Docker. Os presets usam pacotes Debian disponíveis para a arquitetura. Ferramentas extras que você acrescentar ao Dockerfile precisam oferecer suporte à arquitetura escolhida.

Reserve inicialmente 4 GB de RAM para Docker e espaço para imagens, ferramentas e dependências do projeto. Essa é uma alocação inicial sugerida para gateway e memória. A stack e a aplicação podem exigir mais.

No WSL, prefira a pasta do projeto em /home/seu-usuario/dev. Você pode abri-la pelo VS Code Remote WSL ou pelo Explorer em \\wsl.localhost\Ubuntu-24.04\home\seu-usuario\dev. No macOS, permita o compartilhamento da pasta nas configurações do Docker Desktop quando solicitado.

## Instalar

Extraia o ZIP em uma pasta própria, por exemplo ~/dev/openclaw-projeto-kit. Crie uma pasta separada para o código, por exemplo ~/dev/meu-projeto.

No terminal do seu sistema, entre na pasta do kit e execute

~~~bash
python3 setup.py
~~~

O assistente coleta, nesta ordem

1. Nome do novo projeto e caminho da pasta de código existente.
2. Leitura automática de **stack.json**, preenchido com a stack de referência.
3. Porta do painel. As portas das aplicações vêm de development.ports em stack.json.
4. Leitura dos comandos e variáveis em development no mesmo JSON, sem perguntas textuais.
5. Integrações opcionais com GitHub, Linear e Telegram.
6. Equipe padrão de nove agentes, com identidades, instruções e delegação predefinidas em project.example.json.
7. Credenciais próprias de cada integração, solicitadas sem exibição na tela.
8. Provedor de nuvem, modelo padrão e autenticação individual no onboarding do OpenClaw.
9. Aplicação dos modelos predefinidos: Terra 6.1 para arquitetura, frontend, backend-ai, qualidade e devops; Astra para main, produto, ux e cobaia. Cada instalação precisa autenticar uma conta com acesso a esses modelos. Para mudar a escolha, use python3 setup.py models.

Em seguida, ele configura a memória local, cria os agentes escolhidos, aplica as integrações e verifica autenticação dos modelos, acesso ao GitHub, token do Telegram e conexão MCP do Linear. Indexa a descrição do projeto para cada agente, verifica os embeddings, inicia o Gateway e verifica seu endpoint de saúde pelo localhost. A montagem do projeto é testada com um arquivo temporário, lido e alterado dentro do contêiner e conferido no host.

Escolha seu provedor de nuvem na etapa de conversas. O setup específico de memória usa o modo oficial embedding-only. Se o download ou a autenticação falhar, corrija a causa e execute o mesmo comando novamente. O token e os volumes dessa instância são reutilizados.

Para consultar o endereço e o token desta instalação, execute na pasta do kit:

~~~bash
python3 setup.py acesso
~~~

O comando funciona sem Docker em execução e apenas consulta os dados existentes. Ele mostra o endereço com a porta configurada e o token para copiar nas configurações de conexão do painel. Não gera outro token nem reinicia o serviço. O segredo aparece no terminal somente quando esse comando é solicitado; o setup normal apenas informa como consultá-lo.

O painel usa http://localhost:18889 por padrão. Cada instalação gera seu próprio token, salvo em .runtime/.env e preservado nas próximas execuções. Esse arquivo não acompanha o ZIP. Se houver uma solicitação de pareamento do navegador, use

~~~bash
python3 setup.py cli devices list
python3 setup.py cli devices approve ID_DA_SOLICITACAO
~~~

## Onde configurar a stack tecnológica

**Edite stack.json na pasta do kit.** A configuração é declarativa e o setup não pergunta qual é a stack, quais pacotes instalar ou quais comandos executar. Se stack.json ainda não existir, o setup cria-o a partir de stack.example.json. O arquivo stack.schema.json fornece sugestões e validação em editores compatíveis.

A stack de referência inclui Next.js App Router, React, TypeScript estrito, Tailwind, shadcn/ui, Radix, Lucide, React Hook Form, Zod e Firebase. Genkit é uma opção desabilitada por padrão. Ajuste as tecnologias aos requisitos e manifests do projeto.

| Campo em stack.json | Função |
| --- | --- |
| runtime.preset | Ferramentas de linguagem da imagem: node, python, node-python, java, go ou custom. |
| runtime.extra_apt_packages | Pacotes de sistema adicionais para o build. |
| technologies | Linguagens, frontend, backend, UI, formulários, dados e opções de IA da aplicação. |
| structure | Diretórios e organização de referência. |
| quality | Verificações e diretrizes de engenharia. |
| development.ports | Pares host/container para as aplicações. |
| development.install_command | Comando para instalar dependências do projeto. |
| development.dev_commands | Comandos nomeados, por exemplo app, build, lint, typecheck e test. |
| development.environment | Variáveis de ambiente da aplicação. Não coloque credenciais no arquivo compartilhável. |

Exemplo de trecho do JSON

~~~json
{
  "schema_version": 1,
  "name": "Minha stack",
  "runtime": {
    "preset": "node",
    "extra_apt_packages": []
  },
  "technologies": {
    "language": { "name": "TypeScript", "strict": true },
    "frontend": { "framework": "Next.js", "router": "App Router", "ui": "React" }
  },
  "development": {
    "ports": [{ "host": 3000, "container": 3000 }],
    "install_command": "npm install",
    "dev_commands": {
      "app": "npm exec -- next dev --hostname 0.0.0.0 --port 3000"
    },
    "environment": {}
  }
}
~~~

A porta 3000 é o padrão para aplicações de projetos novos. Se a 3000 estiver ocupada, mude o campo host, mantendo container coerente com o comando de desenvolvimento.

project.json guarda nome, pasta de código, porta do painel, integrações e agentes. A única referência à stack nele é

~~~json
{
  "stack_file": "stack.json"
}
~~~

O setup valida o JSON antes de construir a imagem. Ele publica uma cópia em /opt/project-kit/stack.json e em stack.json dentro do workspace de cada agente. AGENTS.md orienta todos os agentes a ler esse documento e não pedir novamente uma descrição da stack. Essas cópias internas são geradas; edite o arquivo de origem no host e execute python3 setup.py para aplicar a alteração.

O JSON define escolhas tecnológicas e comandos, mas não cria sozinho a aplicação ou recursos do Firebase. Em uma pasta vazia, peça ao agente para criar a aplicação seguindo o JSON antes de instalar dependências ou executar comandos de desenvolvimento. Em um repositório existente, preserve seus manifests e lockfile e ajuste o JSON aos comandos reais. Use npm ci quando houver package-lock.json compatível.

Node.js, Git, GitHub CLI e ferramentas de compilação estão disponíveis em todos os presets. Python instala Python/pip/venv, java instala OpenJDK 21/Maven e go instala os pacotes da distribuição da imagem. custom permite acrescentar ferramentas ao Dockerfile. As dependências da aplicação continuam nos manifests e lockfiles do projeto.

Cada instalação configura suas próprias credenciais, contas Firebase/GCP e dados de aplicação. Tecnologias listadas em technologies são contexto para desenvolvimento; runtimes do container são instalados por runtime. Serviços externos exigem configuração própria.

### Atualizar uma instalação do kit anterior

Se project.json ainda usar stack como texto e os antigos campos ports/dev_commands, o setup os migra para um JSON preservando os valores. Salva uma cópia de segurança em project.pre-stack-json.json. Se stack.json já existir, a migração usa stack.legacy.json e aponta stack_file para ele, preservando ambos. Para adotar a base fornecida, revise os arquivos e aponte stack_file para stack.json.

## Integrações opcionais

Use o assistente inicial ou execute novamente

~~~bash
python3 setup.py integrations
~~~

Esse comando reconstrói a imagem usando cache, aplica as escolhas e reinicia apenas esta instância. Para trocar tokens, execute python3 setup.py credentials. As chaves das integrações ficam em .runtime/secrets.json com permissão 0600, fora do código e do contexto de build. Os modelos guardam a autenticação nos volumes próprios do OpenClaw. Quem administra o Docker pode inspecionar as variáveis dos containers.

### GitHub

O instalador pede o repositório no formato DONO/REPOSITORIO e um token pessoal. Crie-o em https://github.com/settings/personal-access-tokens e selecione somente os repositórios que esta instalação deverá acessar.

Para ler código e abrir mudanças, ajuste as permissões Contents, Issues e Pull requests conforme o uso. A instalação verifica leitura do repositório pela API e pela CLI; não faz push nem cria uma issue para testar escrita. Algumas organizações também exigem aprovação do token.

O gh fica instalado na imagem e autenticado por GH_TOKEN. O repositório escolhido é passado por GH_REPO, e o Git usa gh como auxiliar de credenciais para HTTPS. A pasta de código continua sendo a montagem que você escolheu. O setup não clona, altera remotes nem sobrescreve arquivos. Para um projeto novo, peça ao agente para inicializar ou conectar o repositório quando estiver pronto.

O login do GitHub para repositórios é independente da autenticação de modelos do GitHub Copilot.

### Linear

Informe a equipe e, opcionalmente, o projeto de destino, por nome ou UUID. Depois forneça uma chave pessoal criada em Settings > Security & access. A conexão usa o servidor oficial https://mcp.linear.app/mcp com Streamable HTTP.

Escolha read-only para expor apenas ferramentas de consulta, ou read-write para permitir também operações de escrita. O setup executa uma descoberta MCP para verificar conexão e ferramentas. Não cria nem altera tarefas durante a verificação.

Equipe e projeto orientam o agente e precisam corresponder ao destino desejado. Esses campos não são uma barreira de autorização e não são validados contra os nomes existentes durante o setup. Restrinja as permissões e equipes da própria chave para limitar o acesso real. Se precisar garantir somente leitura também pela API, crie a chave com essa restrição.

Essa integração habilita as ferramentas do agente. A sincronização automática de pull requests com tarefas é uma integração separada do GitHub dentro do Linear, não configurada por este kit.

### Telegram

Crie um bot **novo** em https://t.me/BotFather com /newbot. Cole seu token quando solicitado e informe os IDs numéricos das pessoas autorizadas. Não reutilize o bot da instalação antiga, porque duas instâncias consumindo mensagens do mesmo bot entram em conflito.

Os IDs devem ser positivos, como "123456789", e podem ser obtidos por um serviço de identificação no Telegram. Usernames e IDs negativos de grupos não são aceitos neste assistente.

O bot atende conversas privadas dos IDs autorizados e encaminha para main. Grupos ficam desabilitados. Conversas de usuários diferentes têm sessões separadas, mas compartilham o agente e o projeto. Não há isolamento de autorização entre esses colaboradores dentro do mesmo container.

O setup verifica getMe e getWebhookInfo. Se o bot já tiver um webhook, ele para e pede um bot separado. Não remove webhooks nem envia mensagens de teste. A ausência de webhook não permite detectar outra instalação fazendo polling, por isso use um bot novo. O canal recebe mensagens por polling e não exige publicar uma porta adicional na internet.

Após a instalação, abra a conversa com o bot e envie /start. Para conferir o canal

~~~bash
python3 setup.py cli channels status --probe
~~~

### Desabilitar integrações

Execute python3 setup.py integrations, escolha n para a integração e conclua o setup. A configuração do canal Telegram ou servidor MCP Linear gerenciada pelo kit é removida, e as variáveis da integração deixam de ser entregues ao Gateway. As credenciais ficam preservadas localmente para reativação e para carregar a configuração anterior durante a migração. Para revogar o acesso de um token, revogue-o no serviço que o emitiu.

## Modelos e agentes

A memória local utiliza llama.cpp + EmbeddingGemma 300M. Os modelos de conversação e desenvolvimento são remotos. Não há Ollama nem modelo local de chat instalado pelo kit.

O onboarding do OpenClaw autentica o provedor e define o modelo padrão. Depois, o assistente permite conectar outros provedores e consultar seus catálogos. Há suporte do OpenClaw a OpenAI, Anthropic, Google, OpenRouter e outros provedores. O conjunto visível depende da versão instalada, plugins, autenticação e catálogo do provedor.

O kit não inclui créditos nem assinatura. API, OAuth e assinatura são métodos distintos, com disponibilidade e cobrança definidas pelo provedor. Siga o fluxo de autenticação oferecido pelo OpenClaw para sua conta.

| Opção | Comportamento |
| --- | --- |
| Equipe padrão | Chefia (main), Produto, Arquitetura, UX, Frontend, Backend & IA, Qualidade & Segurança, DevOps e Cobaia. |
| Terra 6.1 | arquitetura, frontend, backend-ai, qualidade e devops. |
| Astra | main, produto, ux e cobaia. |
| Delegação | Chefia coordena sete especialistas; Cobaia é independente e acionado diretamente pelo usuário. |
| Modelo explícito | Selecione a referência completa provedor/modelo mostrada no catálogo. |
| Alternativas | Lista ordenada de modelos para fallback, com autenticação própria quando necessário. |
| herdar / model vazio | Usa o modelo padrão global definido no onboarding. |
| Memória | Cada agente tem seu workspace e memória persistentes no volume desta instância. |
| Código | Todos os agentes trabalham sobre a mesma pasta /workspace/project. |

O coordenador recebe permissão para delegar aos especialistas escolhidos. Eles recebem suas funções em AGENTS.md e não podem delegar a outros agentes pelo kit. O contexto orienta a coordenar edições para evitar conflitos. O kit não cria worktrees nem uma fila automática de trabalho.

A equipe padrão usa sua conta ChatGPT autenticada pelo Codex. A configuração `model_routes: {"openai/gpt-6.1-terra": "chatgpt"}` registra a rota de assinatura apenas para Terra, contornando a incompatibilidade de descoberta do OpenClaw 2026.11.3 ([relato upstream](https://github.com/openclaw/openclaw/issues/185064)). A inicialização da configuração do plugin é preparada antes do patch; a validação oficial continua ativa. Para adotar outra rota de autenticação, revise também essa opção e a declaração do modelo no OpenClaw.

Para selecionar novamente os modelos

~~~bash
python3 setup.py models
~~~

Para consultar sem reconfigurar

~~~bash
python3 setup.py cli models list --all
python3 setup.py cli models list --provider openai
python3 setup.py cli models status --agent main
python3 setup.py cli agents list
~~~

**project.json** contém a lista agents, com id, role, model e fallbacks. Um model vazio herda o padrão; com modelo explícito, fallbacks vazio significa que não haverá troca automática para outro modelo. Também é possível definir apenas fallbacks com model vazio para herdar o principal e substituir suas alternativas.

Agentes importados também podem definir `name`, `identity`, `thinkingDefault`, `params.maxTokens` e `delegates`. A lista `delegates` limita a delegação aos IDs presentes nesta instalação; uma lista vazia mantém o agente independente. Referências de modelo podem incluir o perfil de autenticação no formato `provedor/modelo@perfil`.

O campo `workspace_files` aceita o conteúdo de `AGENTS.md`, `SOUL.md`, `IDENTITY.md` e `TEAM_PLAYBOOK.md`. Na primeira aplicação, arquivos existentes recebem uma cópia `.pre-import`; as execuções seguintes preservam edições no workspace. A equipe padrão, seus modelos e instruções portáveis ficam em project.example.json e acompanham o pacote. Alterações individuais ficam em project.json, excluído do ZIP. Memórias, sessões e credenciais existentes não são distribuídas.

### Definições revisadas da equipe

As definições portáveis da equipe incorporam a revisão de 15/11/2026: atribuições delimitadas, especialistas sob demanda, revisão independente, evidências por revisão/ambiente, testes negativos de autorização e tenants, verificação de interação da UI e tratamento de ferramentas indisponíveis sem sucesso inventado. Frontend limita alterações de caches e ferramentas ao escopo autorizado; Backend/Qualidade não podem contornar uma negativa alterando proxy ou controles de rede. Cobaia continua independente. Cada agente recebe AGENTS.md, SOUL.md e uma cópia acessível do playbook.

As definições são portáveis: usam os caminhos do contêiner, a stack do projeto e as integrações efetivamente configuradas. Não pressupõem o Project privado de outra instalação nem criam contas, projetos ou permissões por causa de nomes citados no texto. Sem tracker configurado, o contrato de execução fica no projeto e a ausência de sincronização externa é declarada. Com GitHub ou Linear, a coordenação segue o destino autorizado desta instalação. A política Vertex exige configuração e autorização próprias; nenhuma credencial ou conta é importada.

Em instalações novas, o setup lê esse modelo de equipe. Atualizar os arquivos do kit não substitui automaticamente os `workspace_files` de um project.json existente nem as instruções já importadas: a marca `.project-kit-imported` preserva personalizações. Para adotar as novas definições em uma instalação existente, compare o modelo novo com project.json e os arquivos do workspace, faça backup e mescle somente os trechos desejados; executar novamente o setup sozinho não força a reimportação. Mudanças em modelos, alternativas ou permissões não fazem parte dessa atualização das instruções.

Ao editar modelos manualmente, use referências do catálogo e mantenha models_configured como true para aplicar sua seleção sem repetir o assistente. Configure como false ou execute o comando models para escolher novamente. Credenciais continuam sendo configuradas pelo OpenClaw.

Para adicionar um agente, acrescente sua entrada em agents e execute o setup. Use IDs simples em minúsculas e preserve main. Retirar uma entrada do arquivo não apaga um agente já criado nem seu histórico; o kit deixa de gerenciá-lo e de incluí-lo na lista de delegação do main. A exclusão deliberada deve ser feita depois pela CLI de agentes do OpenClaw.

Os modelos escolhidos passam por models status --check. Essa verificação detecta autenticação ausente, expirada ou runtime indisponível, mas não executa inferência e não garante saldo ou acesso efetivo a toda variante do catálogo. Quando houver falha, o setup para antes de iniciar o Gateway e mostra o agente a corrigir. Para uma conta específica

~~~bash
python3 setup.py cli models auth --agent qualidade add
python3 setup.py
~~~

Se quiser um teste real de modelos, que pode consumir créditos, pare o Gateway antes do probe e reinicie ao terminar

~~~bash
python3 setup.py stop
python3 setup.py cli models status --agent main --probe
python3 setup.py start
~~~

A seleção de modelos por agente não copia agentes, memórias ou credenciais da instalação antiga.


## Pasta compartilhada e portas

| Recurso | Host | Contêiner |
| --- | --- | --- |
| Código | project_dir | /workspace/project |
| Painel | localhost:18889 por padrão | 18789 |
| Aplicações | development.ports[].host em localhost | development.ports[].container |
| Memória, sessões e plugins | Volume Docker exclusivo da instância | /home/node/.openclaw |
| Cache de ferramentas | Volume Docker exclusivo | /home/node/.cache |
| Dados de autenticação auxiliares | Volume Docker exclusivo | /home/node/.config/openclaw |

Os arquivos do código são compartilhados em leitura e escrita. Editar no editor do host ou pelo agente modifica a mesma pasta. O workspace de memória do agente fica no volume de estado. O setup acrescenta a ele a descrição da stack e orienta o agente a trabalhar em /workspace/project.

No Linux e no WSL, a imagem usa UID/GID do usuário que fez o setup para que os arquivos criados pertençam a ele. No Docker Desktop para Mac, o compartilhamento é gerenciado pelo Docker.

Todas as portas publicadas usam 127.0.0.1 no host. Dentro do contêiner, sua aplicação deve escutar em **0.0.0.0**. Por exemplo, um mapeamento com host 15173 e container 5173 permite abrir http://localhost:15173 enquanto o Vite escuta internamente na porta 5173.

Para dois projetos simultâneos, escolha portas de host diferentes. O setup verifica conflitos antes de subir o serviço.

As dependências de aplicação, como node_modules e .venv, são geradas para Linux e persistem na pasta compartilhada. Execute os comandos de desenvolvimento pelo contêiner ao usar essas dependências. Para problemas de hot reload no Docker Desktop, configure no projeto o mecanismo de polling do framework. Por exemplo, CHOKIDAR_USEPOLLING pode ser definido como "true" em development.environment quando a ferramenta usa Chokidar.

A referência host.docker.internal é disponibilizada para acessar um serviço que você decidiu executar no host. Esse serviço precisa aceitar conexões vindas da rede Docker. O funcionamento desse acesso depende do SO e do endereço de escuta do serviço.

## Trabalhar no projeto

Instale as dependências definidas em development.install_command

~~~bash
python3 setup.py install
~~~

Inicie cada aplicação em um terminal

~~~bash
python3 setup.py dev app
~~~

Os comandos dev ficam em primeiro plano. Ctrl+C encerra o processo daquela aplicação. O Gateway permanece supervisionado pelo Docker. Depois de reiniciar o contêiner, inicie novamente os processos de desenvolvimento.

Outros comandos

~~~bash
python3 setup.py status
python3 setup.py logs
python3 setup.py shell
python3 setup.py stop
python3 setup.py start
python3 setup.py cli models status
python3 setup.py cli devices list
~~~

Para preparar project.json e stack.json, execute python3 setup.py configure. O Docker é usado no setup completo.

## Conferir a instalação

O setup executa config validate, models status --check para cada agente, os testes de integrações habilitadas, memory index e memory status --deep para cada agente, o healthcheck da imagem e uma chamada HTTP ao painel pelo localhost.

Para repetir os testes de acesso, execute python3 setup.py check. Esse comando para temporariamente o Gateway porque os probes MCP exigem acesso exclusivo, executa verificações de leitura e restaura o Gateway se ele estava rodando. Não envia mensagens nem cria tarefas ou pull requests. Leia os diagnósticos de memória para confirmar que EmbeddingGemma está disponível.

Depois de iniciar uma aplicação, abra sua porta publicada no navegador do host. Crie um arquivo de teste pelo editor do host e confira-o com python3 setup.py shell. Peça ao agente para alterar esse arquivo e confira a alteração no editor. Reinicie o Gateway e confirme a persistência da conversa e da memória.

Os comandos de indexação e diagnóstico profundo de memória exigem que o Gateway esteja parado. O setup já segue essa ordem. Para repetir esse diagnóstico depois, execute python3 setup.py stop, depois python3 setup.py cli memory status --deep --agent main e, ao concluir, python3 setup.py start.

## Compartilhar e preservar dados

Distribua o ZIP fornecido ou gere um pacote limpo usando

~~~bash
python3 setup.py package
~~~

O arquivo dist/openclaw-projeto-container.zip inclui apenas Dockerfile, setup.py, features.py, seed.mjs, verify-integrations.mjs, README.md, AGENTS.md, project.example.json, .gitignore, .dockerignore stack_config.py, stack.example.json, stack.schema.json, runtime-config-preload.mjs e os três arquivos de testes. project.json, stack.json personalizado, .runtime, volumes e arquivos extras ficam fora do pacote. A stack de referência compartilhável está em stack.example.json. Cada pessoa fará seu próprio setup.

Para atualizar uma cópia do kit anterior, substitua somente esses arquivos distribuídos, preservando project.json, stack.json e .runtime, e execute python3 setup.py. O assistente coleta as novas opções. Não extraia sobre a pasta de código nem sobre o diretório da instalação antiga do OpenClaw.

project.json, .runtime e os volumes pertencem à instalação individual. Eles podem conter caminhos, tokens e credenciais. Faça backups privados do estado e do código antes de atualizar versões. O comando stop conserva os volumes. Apagar volumes pelo Docker remove seus dados.

Para criar outra instância, extraia uma cópia nova do ZIP em outra pasta e escolha o caminho do novo projeto. O identificador aleatório gerado no primeiro setup evita compartilhar acidentalmente volumes entre instalações com nomes iguais.

Foram executados 22 testes Python e 8 verificações JavaScript, cobrindo configuração, isolamento de credenciais, modelos e alternativas, equipe padrão de novas instalações, retomada, bloqueio em caso de erro, importação de identidades e instruções, limites de delegação, preservação de edições e exclusão de dados pessoais do pacote. As chamadas externas são simuladas nesses testes. O Compose gerado com as três integrações passou na validação da ferramenta oficial Docker Compose.

Para repetir os testes locais, com Python 3.10+ e Node 22+ disponíveis

~~~bash
python3 -m unittest -v test_setup test_stack_config
node test_feature_scripts.mjs
~~~

A instalação real foi validada em WSL/Linux x86_64, com autenticação ChatGPT, nove agentes, indexação e embeddings de cada agente, montagem do código, Gateway saudável e resposta real do Terra 6.1 pelo Codex. Isso não constitui teste de uma instalação nova em outro computador. Linux nativo e macOS, incluindo ARM64, ainda precisam de validação ponta a ponta. A CI executa testes locais simulados e gera o ZIP; não realiza login nem inferência.

## Referências oficiais

- [Instalação Docker](https://docs.openclaw.ai/install/docker)
- [llama.cpp e modo embedding-only](https://docs.openclaw.ai/plugins/llama-cpp)
- [CLI de memória](https://docs.openclaw.ai/cli/memory)
- [Perfil de ferramentas para programação](https://docs.openclaw.ai/gateway/config-tools/tool-policy)
- [Boas práticas Docker no WSL2](https://docs.docker.com/desktop/features/wsl/best-practices/)
- [Publicação de portas Docker](https://docs.docker.com/engine/network/port-publishing/)

- [Configuração de modelos e autenticação](https://docs.openclaw.ai/cli/models)
- [Agentes e delegação](https://docs.openclaw.ai/cli/agents)
- [MCP no OpenClaw](https://docs.openclaw.ai/cli/mcp/registry)
- [MCP oficial do Linear](https://linear.app/docs/mcp)
- [GitHub CLI e autenticação](https://cli.github.com/manual/gh_auth_login)
- [Telegram no OpenClaw](https://docs.openclaw.ai/channels/telegram/setup)
