"""Integrações opcionais e seleção de modelos para a instância deste kit."""
import getpass
import json
from pathlib import Path
import re
import subprocess
import sys

SECRET_KEYS = {"github": "GH_TOKEN", "linear": "LINEAR_API_KEY", "telegram": "TELEGRAM_BOT_TOKEN"}
LOCAL_PROVIDERS = {"ollama", "llama-cpp", "lmstudio", "vllm", "sglang", "omlx", "llmman"}
ROLES = {
    "main": "Coordene o projeto e converse com o usuário. Delegue tarefas delimitadas aos especialistas configurados.",
    "arquitetura": "Avalie arquitetura, contratos e decisões técnicas. Explique implicações antes de grandes mudanças.",
    "desenvolvimento": "Implemente tarefas na stack do projeto e execute as verificações pertinentes.",
    "revisao": "Revise mudanças, regressões e critérios de aceite. Apresente evidências e testes reproduzíveis.",
}


def yes(ask, label, default=False):
    value = ask(label + " (s/n)", "s" if default else "n").lower()
    if value not in {"s", "n", "sim", "nao", "não"}:
        raise ValueError("Responda s ou n.")
    return value in {"s", "sim"}


def remote_ref(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:/+-]*(?:@[A-Za-z0-9][A-Za-z0-9._:@+-]*)?", value):
        raise ValueError("Use a referência completa provedor/modelo mostrada pelo catálogo.")
    if value.split("/", 1)[0] in LOCAL_PROVIDERS:
        raise ValueError("Este kit usa modelos remotos para agentes e llama.cpp apenas para memória.")
    return value


def validate(config):
    routes = config.get("model_routes", {})
    if not isinstance(routes, dict) or set(routes) - {"openai/gpt-6.1-terra"} or any(v != "chatgpt" for v in routes.values()):
        raise ValueError("model_routes aceita openai/gpt-6.1-terra: chatgpt para a compatibilidade de assinatura.")
    integrations = config.setdefault("integrations", {})
    if not isinstance(integrations, dict) or set(integrations) - set(SECRET_KEYS):
        raise ValueError("Integrações aceitas: github, linear, telegram.")
    allowed = {
        "github": {"enabled", "repository"},
        "linear": {"enabled", "team", "project", "access"},
        "telegram": {"enabled", "allowed_user_ids"},
    }
    for name in SECRET_KEYS:
        item = integrations.setdefault(name, {"enabled": False})
        if not isinstance(item, dict) or set(item) - allowed[name]:
            raise ValueError(f"Campos inválidos em integrations.{name}. Credenciais são solicitadas separadamente.")
        if not isinstance(item.get("enabled", False), bool):
            raise ValueError(f"integrations.{name}.enabled deve ser true ou false.")
    gh = integrations["github"]
    if gh.get("enabled") and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", gh.get("repository", "")):
        raise ValueError("GitHub exige repository no formato DONO/REPOSITORIO.")
    linear = integrations["linear"]
    if linear.get("enabled"):
        if linear.get("access", "read-write") not in {"read-only", "read-write"}:
            raise ValueError("Linear access deve ser read-only ou read-write.")
        for field in ("team", "project"):
            if not isinstance(linear.get(field, ""), str) or len(linear.get(field, "")) > 200:
                raise ValueError(f"Linear {field} deve ser nome ou UUID com até 200 caracteres.")
        if not linear.get("team", "").strip():
            raise ValueError("Informe a equipe de destino do Linear.")
    tg = integrations["telegram"]
    if tg.get("enabled"):
        ids = tg.get("allowed_user_ids", [])
        if not isinstance(ids, list) or not ids or any(
            not isinstance(i, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", i) for i in ids
        ):
            raise ValueError("Telegram exige allowed_user_ids como lista de IDs numéricos positivos em texto.")
    agents = config.setdefault("agents", [{"id": "main", "role": ROLES["main"], "model": "", "fallbacks": []}])
    if not isinstance(agents, list) or not agents:
        raise ValueError("Informe ao menos o agente main.")
    ids = set()
    for agent in agents:
        if not isinstance(agent, dict) or set(agent) - {"id", "role", "model", "fallbacks", "name", "identity", "thinkingDefault", "params", "delegates", "workspace_files"}:
            raise ValueError("Campos de agente inválidos.")
        aid = agent.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", aid) or aid in {"openclaw", "crestodian"} or aid in ids:
            raise ValueError("ID de agente inválido, reservado ou duplicado.")
        ids.add(aid)
        if "name" in agent and (not isinstance(agent["name"], str) or not agent["name"].strip()):
            raise ValueError("Nome de agente inválido.")
        if "identity" in agent and (not isinstance(agent["identity"], dict) or
                set(agent["identity"]) - {"name", "emoji", "theme", "avatar"} or
                any(not isinstance(v, str) for v in agent["identity"].values())):
            raise ValueError("Identidade de agente inválida.")
        if "thinkingDefault" in agent and agent["thinkingDefault"] not in {"off", "minimal", "low", "medium", "high", "xhigh", "adaptive"}:
            raise ValueError("Nível de raciocínio inválido.")
        if "params" in agent and (not isinstance(agent["params"], dict) or set(agent["params"]) - {"maxTokens"} or
                any(type(v) is not int or v <= 0 for v in agent["params"].values())):
            raise ValueError("Parâmetros de agente inválidos.")
        files = agent.get("workspace_files", {})
        if not isinstance(files, dict) or set(files) - {"AGENTS.md", "SOUL.md", "IDENTITY.md", "TEAM_PLAYBOOK.md"} or any(not isinstance(v, str) for v in files.values()):
            raise ValueError("Arquivos de instruções inválidos.")
        if not isinstance(agent.get("role"), str) or not agent["role"].strip():
            raise ValueError("Cada agente precisa de uma descrição em role.")
        if not isinstance(agent.get("model", ""), str):
            raise ValueError("model deve ser texto ou vazio para herdar.")
        if agent.get("model"):
            remote_ref(agent["model"])
        if not isinstance(agent.get("fallbacks", []), list):
            raise ValueError("fallbacks deve ser uma lista de referências provedor/modelo.")
        for model in agent.get("fallbacks", []):
            remote_ref(model)
    if "main" not in ids:
        raise ValueError("Preserve o agente main como coordenador e destino do Telegram.")
    for agent in agents:
        delegates = agent.get("delegates", [])
        if not isinstance(delegates, list) or any(not isinstance(a, str) or a not in ids or a == agent["id"] for a in delegates):
            raise ValueError("Delegação deve referenciar outros agentes desta instalação.")
    if not isinstance(config.get("models_configured", False), bool):
        raise ValueError("models_configured deve ser true ou false.")
    return config


def configure(config, ask):
    print("\nIntegrações opcionais — cada instalação usa suas próprias contas")
    previous = config.get("integrations", {})
    settings = {}
    for name, label in (("github", "GitHub"), ("linear", "Linear"), ("telegram", "Telegram")):
        old = previous.get(name, {})
        item = {"enabled": yes(ask, "Habilitar " + label, old.get("enabled", False))}
        if item["enabled"]:
            if name == "github":
                item["repository"] = ask("Repositório DONO/REPOSITORIO", old.get("repository", ""))
            elif name == "linear":
                item["team"] = ask("Equipe Linear (nome ou UUID)", old.get("team", ""))
                item["project"] = ask("Projeto Linear (nome/UUID, opcional)", old.get("project", ""))
                item["access"] = ask("Acesso Linear: read-only ou read-write", old.get("access", "read-write"))
            else:
                print("Crie um bot NOVO em https://t.me/BotFather usando /newbot.")
                print("Informe IDs de pessoas, não usernames nem IDs negativos de grupos.")
                item["allowed_user_ids"] = [v.strip() for v in ask(
                    "IDs dos usuários autorizados, separados por vírgula",
                    ",".join(old.get("allowed_user_ids", []))).split(",") if v.strip()]
        settings[name] = item
    config["integrations"] = settings
    if "agents" not in config:
        template = json.loads(Path(__file__).with_name("project.example.json").read_text(encoding="utf-8"))
        config["agents"] = template["agents"]
        config["models_configured"] = template["models_configured"]
        config["model_routes"] = template.get("model_routes", {})
        print("Equipe padrão: " + ", ".join(a["name"] for a in config["agents"]))
        print("Modelos predefinidos: Terra 6.1 e Astra. Use python3 setup.py models para trocar.")
    config["kit_version"] = max(config.get("kit_version", 2), 2)
    return validate(config)


def read_secrets(runtime):
    path = runtime / "secrets.json"
    if not path.exists():
        return {}
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict) or set(values) - set(SECRET_KEYS.values()):
        raise ValueError("Arquivo de credenciais do kit inválido.")
    for key, value in values.items():
        if not isinstance(value, str) or not value or any(c.isspace() for c in value):
            raise ValueError(f"Credencial inválida para {key}. Use python3 setup.py credentials.")
    return values


def collect_secrets(config, runtime, write_json, rotate=False):
    values = read_secrets(runtime)
    for name, key in SECRET_KEYS.items():
        if not config["integrations"][name].get("enabled"):
            continue
        if values.get(key) and not rotate:
            continue
        if not sys.stdin.isatty():
            raise ValueError("Credenciais ausentes. Execute o setup num terminal interativo.")
        if name == "github":
            print("GitHub: crie um token limitado ao repositório em https://github.com/settings/personal-access-tokens")
            print("Para desenvolver: Contents, Issues e Pull requests conforme o acesso desejado.")
        elif name == "linear":
            print("Linear: crie sua chave em Settings > Security & access > Personal API keys.")
        else:
            print("Telegram: cole o token do bot novo criado no BotFather.")
        value = getpass.getpass(key + (" (Enter mantém a atual)" if values.get(key) else "") + ": ").strip()
        if not value and values.get(key):
            continue
        if not value or any(c.isspace() for c in value):
            raise ValueError("Token vazio ou com espaços.")
        if name == "telegram" and not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", value):
            raise ValueError("Formato do token Telegram inválido.")
        values[key] = value
        write_json(runtime / "secrets.json", values)


def environment(config):
    result = {}
    for name, key in SECRET_KEYS.items():
        if config.get("integrations", {}).get(name, {}).get("enabled"):
            result[key] = "$" + "{" + key + ":?Credencial ausente}"
    github = config.get("integrations", {}).get("github", {})
    if github.get("enabled"):
        result["GH_REPO"] = github["repository"]
        result["GH_PROMPT_DISABLED"] = "1"
        result["GH_CONFIG_DIR"] = "/home/node/.config/openclaw/gh"
    return result


def workspace(aid):
    return "/home/node/.openclaw/" + ("workspace" if aid == "main" else "workspace-" + aid)


def patch(config, state=None):
    entries = {}
    ids = [a["id"] for a in config["agents"]]
    for agent in config["agents"]:
        aid = agent["id"]
        entry = {
            "name": agent.get("name", aid), "workspace": workspace(aid),
            "subagents": {"allowAgents": agent.get("delegates", [i for i in ids if i != "main"] if aid == "main" else [])},
        }
        for key in ("identity", "thinkingDefault", "params"):
            if key in agent:
                entry[key] = agent[key]
        entry["model"] = ({"primary": agent["model"], "fallbacks": agent.get("fallbacks", [])}
                          if agent.get("model") else ({"fallbacks": agent["fallbacks"]} if agent.get("fallbacks") else None))
        entries[aid] = entry
    result = {"agents": {"defaults": {"systemAgent": {"agentId": "main"}}, "entries": entries},
              "session": {"dmScope": "per-channel-peer"}}
    selected = {ref.split("@", 1)[0] for a in config["agents"] for ref in [a.get("model", ""), *a.get("fallbacks", [])]}
    if config.get("model_routes", {}).get("openai/gpt-6.1-terra") == "chatgpt" and "openai/gpt-6.1-terra" in selected:
        # 2026.11.3 discovers Terra in Codex but lacks its subscription transport.
        # Author only this model's route; do not change the provider-wide API/URL.
        models = [m for m in (state or {}).get("openaiModels", []) if m.get("id") != "gpt-6.1-terra"]
        models.append({"id": "gpt-6.1-terra", "name": "GPT-6.1 Terra",
                       "api": "openai-chatgpt-responses", "reasoning": True,
                       "input": ["text", "image"], "contextWindow": 872000,
                       "contextTokens": 500000, "maxTokens": 128000})
        result["models"] = {"providers": {"openai": {"models": models}}}
    if any("delegates" in a for a in config["agents"]):
        result["agents"]["defaults"]["subagents"] = {"maxChildrenPerAgent": max(1, max(len(e["subagents"]["allowAgents"]) for e in entries.values()))}
    integrations = config["integrations"]
    linear = integrations["linear"]
    if linear.get("enabled"):
        url = "https://mcp.linear.app/mcp" + ("/readonly" if linear.get("access") == "read-only" else "")
        result["mcp"] = {"servers": {"linear": {
            "enabled": True, "url": url, "transport": "streamable-http",
            "headers": {"Authorization": "Bearer $" + "{LINEAR_API_KEY}"},
        }}}
    else:
        result["mcp"] = {"servers": {"linear": None}}
    tg = integrations["telegram"]
    result["channels"] = {"telegram": {
        "enabled": True, "botToken": "$" + "{TELEGRAM_BOT_TOKEN}", "tokenFile": None,
        "dmPolicy": "allowlist", "allowFrom": tg["allowed_user_ids"],
        "groupPolicy": "disabled",
    }} if tg.get("enabled") else {"telegram": None}
    return result


def select_models(kit, config, project, force=False):
    if config.get("models_configured") and not force:
        return
    if not sys.stdin.isatty():
        raise ValueError("Execute num terminal para escolher modelos, ou configure agents e models_configured em project.json.")
    print("\nModelos e contas — os nomes disponíveis dependem dos provedores conectados.")
    print("O catálogo não garante permissão ou saldo. As verificações de autenticação ocorrem depois.")
    while yes(kit.ask, "Conectar mais um provedor ou revisar autenticação"):
        project.offline("configure", "--section", "model")
    catalog = set(project.offline("models", "list", "--refresh", "--all", "--plain", capture=True).splitlines())
    catalog = {line.strip() for line in catalog if re.fullmatch(r"[a-z0-9][a-z0-9._-]*/\S+", line.strip())}
    if not catalog:
        raise ValueError("Catálogo vazio. Revise a autenticação com cli configure --section model.")
    providers = sorted({m.split("/", 1)[0] for m in catalog if m.split("/", 1)[0] not in LOCAL_PROVIDERS})
    print("Provedores no catálogo: " + ", ".join(providers))
    project.offline("models", "status", "--agent", "main")
    while True:
        provider = kit.ask("Provedor para listar modelos (Enter continua)")
        if not provider:
            break
        if provider not in providers:
            print("Provedor ausente no catálogo.")
            continue
        project.offline("models", "list", "--refresh", "--provider", provider)
    print("\nEscolha provedor/modelo para cada agente. Digite herdar para usar o padrão do onboarding.")
    for agent in config["agents"]:
        value = kit.ask("Modelo de " + agent["id"], agent.get("model") or "herdar")
        if value.lower() == "herdar":
            agent["model"], agent["fallbacks"] = "", []
            continue
        remote_ref(value)
        if value.split("@", 1)[0] not in catalog:
            raise ValueError(f"Modelo {value} ausente do catálogo. Conecte o provedor e repita python3 setup.py models.")
        agent["model"] = value
        fallback = kit.ask("Alternativas em ordem, separadas por vírgula (nenhuma para limpar)",
                           ",".join(agent.get("fallbacks", [])) or "nenhuma")
        agent["fallbacks"] = [] if fallback.lower() == "nenhuma" else [s.strip() for s in fallback.split(",")]
        for model in agent["fallbacks"]:
            remote_ref(model)
            if model.split("@", 1)[0] not in catalog:
                raise ValueError(f"Alternativa {model} ausente do catálogo.")
    validate(config)
    config["models_configured"] = True
    kit.write_json(kit.CONFIG, config)


def create_agents(config, project, state):
    existing = state.get("agents", {}).get("entries", {})
    for agent in config["agents"]:
        aid = agent["id"]
        if aid not in existing:
            project.offline("agents", "add", aid, "--workspace", workspace(aid), "--non-interactive")


def verify_models(config, project):
    for agent in config["agents"]:
        aid = agent["id"]
        try:
            project.offline("models", "status", "--agent", aid, "--check")
        except subprocess.CalledProcessError as error:
            raise ValueError(
                f"Modelo de {aid} sem prontidão confirmada. Use "
                f"python3 setup.py cli models auth --agent {aid} add, "
                "ou python3 setup.py models para rever a escolha. "
                "O diagnóstico acima distingue falta de autenticação, expiração e runtime indisponível."
            ) from error


def context(config):
    lines = [
        "\n## Integrações deste projeto",
        "As integrações abaixo foram escolhidas pelo usuário. Nunca mostre tokens em respostas, logs ou arquivos do código.",
        "Use GitHub CLI (gh) para GitHub e as ferramentas MCP linear para Linear quando habilitados.",
        "Os campos de repositório/equipe/projeto definem o destino de trabalho; os limites reais de acesso são os das credenciais.",
        "Não altere outros projetos. Só publique, envie mensagens ou altere tarefas externas quando solicitado pelo usuário.",
        json.dumps(config["integrations"], ensure_ascii=False, indent=2),
        "\n## Colaboração",
        "Todos os agentes compartilham /workspace/project. Coordene alterações para evitar edições simultâneas nos mesmos arquivos.",
        "O coordenador pode delegar aos especialistas configurados. Cada agente mantém seu próprio workspace e memória.",
        "Agentes configurados: " + ", ".join(a["id"] for a in config["agents"]),
    ]
    return "\n".join(lines) + "\n"
