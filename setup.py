#!/usr/bin/env python3
"""OpenClaw por projeto. Requer Python 3.10+ e Docker Compose v2 no host."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import features
import stack_config

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "project.json"
RUNTIME = ROOT / ".runtime"
BOOTSTRAP = RUNTIME / "bootstrap"
IMAGE = "ghcr.io/openclaw/openclaw:2026.11.3@sha256:e73f689d663567f0fe3c5a85c54beb3e102dc21f0814bf375e9039ee2d2df51b"
EMBEDDING = "hf:ggml-org/embeddinggemma-300m-qat-q8_0-GGUF/embeddinggemma-300m-qat-Q8_0.gguf"
STACKS = {
    "node": ("Node.js / TypeScript", []),
    "python": ("Python", ["python3", "python3-pip", "python3-venv", "python3-dev"]),
    "node-python": ("Node.js + Python", ["python3", "python3-pip", "python3-venv", "python3-dev"]),
    "java": ("Java 21 + Maven", ["openjdk-21-jdk-headless", "maven"]),
    "go": ("Go", ["golang-go"]),
    "custom": ("Personalizada no Dockerfile", []),
}


def write_atomic(path, text, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    if path == CONFIG and isinstance(value, dict) and "stack_file" in value:
        value = stack_config.project_fields(value)
    write_atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def ask(label, default=""):
    value = input(label + (f" [{default}]" if default else "") + ": ").strip()
    return value or default


def port_number(value):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f"Porta inválida: {value}")
    value = int(value)
    if not 1024 <= value <= 65535:
        raise ValueError("Use portas de 1024 a 65535.")
    return value


def validate(config):
    stack_config.hydrate(config, ROOT)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", config.get("name", "")):
        raise ValueError("Nome deve usar até 40 letras minúsculas, números e hífens.")
    if config.get("stack") not in STACKS:
        raise ValueError("Stack deve ser uma das opções " + ", ".join(STACKS))
    project = Path(config["project_dir"]).expanduser()
    if not project.is_absolute():
        project = ROOT / project
    project = project.resolve()
    if project == Path(project.anchor) or project == Path.home().resolve():
        raise ValueError("Escolha a pasta específica do projeto.")
    if any(p == ".openclaw" or p.startswith(".openclaw-") for p in project.parts):
        raise ValueError("Escolha uma pasta de código fora de instalações OpenClaw.")
    if project == ROOT or project in ROOT.parents or ROOT in project.parents:
        raise ValueError("Extraia o kit e mantenha a pasta do projeto como diretórios separados.")
    if not project.is_dir():
        raise ValueError(f"Crie a pasta do projeto antes do setup: {project}")
    config["project_dir"] = str(project)
    config["gateway_port"] = port_number(config.get("gateway_port", 18889))
    seen_host = {config["gateway_port"]}
    seen_container = {18789}
    for item in config.get("ports", []):
        item["host"] = port_number(item["host"])
        item["container"] = port_number(item["container"])
        if item["host"] in seen_host or item["container"] in seen_container:
            raise ValueError("Há portas duplicadas ou conflito com a porta do Gateway.")
        seen_host.add(item["host"])
        seen_container.add(item["container"])
    for package in config.get("extra_apt_packages", []):
        if not isinstance(package, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.+:=~-]*", package):
            raise ValueError(f"Pacote apt inválido: {package}")
    if not isinstance(config.get("dev_commands", {}), dict):
        raise ValueError("dev_commands deve ser um objeto nome/comando.")
    for name, command in config.get("dev_commands", {}).items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not isinstance(command, str):
            raise ValueError("Cada comando de desenvolvimento precisa de nome e texto válidos.")
    if not isinstance(config.get("install_command", ""), str):
        raise ValueError("install_command deve ser texto.")
    for name, value in config.get("environment", {}).items():
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name) or not isinstance(value, str):
            raise ValueError("Variáveis de ambiente devem ter nome maiúsculo e valor textual.")
        if name.startswith(("OPENCLAW_", "DOCKER_", "COMPOSE_")) or name in {
            "HOME", "PATH", "NODE_OPTIONS", "LD_PRELOAD", "LD_LIBRARY_PATH",
            "GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_CONFIG_DIR", "LINEAR_API_KEY", "TELEGRAM_BOT_TOKEN"
        }:
            raise ValueError(f"Variável reservada pelo runtime: {name}")
    image = config.get("openclaw_image", IMAGE)
    if not re.fullmatch(r"ghcr\.io/openclaw/openclaw:[a-zA-Z0-9_.-]+@sha256:[a-f0-9]{64}", image):
        raise ValueError("Use uma imagem oficial com versão e digest SHA-256.")
    config["openclaw_image"] = image
    return features.validate(config)


def configure():
    if CONFIG.exists():
        config = stack_config.read(CONFIG)
        if config.get("kit_version", 1) < 2:
            features.configure(config, ask)
        config["stack_file"] = stack_config.ensure(sys.modules[__name__], config)
        config["kit_version"] = 3
        validate(config)
        write_json(CONFIG, config)
        return config
    print("\nConfiguração do NOVO projeto")
    stack_file = stack_config.ensure(sys.modules[__name__])
    name = ask("Nome do projeto", "meu-projeto")
    directory = ask("Pasta existente do código no host", str(ROOT.parent / name))
    gateway = ask("Porta localhost para o painel OpenClaw", "18889")
    config = {
        "name": name, "project_dir": directory, "stack_file": stack_file,
        "gateway_port": gateway, "openclaw_image": IMAGE,
    }
    features.configure(config, ask)
    config["kit_version"] = 3
    validate(config)
    write_json(CONFIG, config)
    return config


def local_identity():
    if sys.platform == "darwin":
        return 1000, 1000
    if sys.platform.startswith("linux"):
        if os.getuid() == 0:
            raise ValueError("Execute como seu usuário normal para manter a autoria dos arquivos.")
        return os.getuid(), os.getgid()
    raise ValueError("No Windows, execute o kit no terminal Linux do WSL2.")


def literal(value):
    return str(value).replace("$", "$$")


def compose_document(config, instance, uid, gid):
    published = [{"target": 18789, "published": str(config["gateway_port"]),
                  "host_ip": "127.0.0.1", "protocol": "tcp"}]
    published.extend({"target": p["container"], "published": str(p["host"]),
                      "host_ip": "127.0.0.1", "protocol": "tcp"} for p in config.get("ports", []))
    environment = {key: literal(value) for key, value in config.get("environment", {}).items()}
    environment.update({
        "HOME": "/home/node", "OPENCLAW_STATE_DIR": "/home/node/.openclaw",
        "OPENCLAW_CONFIG_PATH": "/home/node/.openclaw/openclaw.json",
        "OPENCLAW_GATEWAY_PORT": "18789",
        "OPENCLAW_GATEWAY_TOKEN": "$" + "{OPENCLAW_GATEWAY_TOKEN:?Token ausente}",
        "OPENCLAW_DISABLE_BONJOUR": "1", "XDG_CACHE_HOME": "/home/node/.cache",
        "NPM_CONFIG_CACHE": "/home/node/.cache/npm", "PIP_CACHE_DIR": "/home/node/.cache/pip",
    })
    environment.update(features.environment(config))
    packages = STACKS[config["stack"]][1] + config.get("extra_apt_packages", [])
    return {
        "name": instance,
        "services": {"openclaw": {
            "build": {"context": literal(ROOT), "dockerfile": "Dockerfile",
                      "args": {"OPENCLAW_IMAGE": config["openclaw_image"],
                               "LOCAL_UID": str(uid), "LOCAL_GID": str(gid),
                               "STACK_APT_PACKAGES": " ".join(dict.fromkeys(packages))}},
            "init": True, "restart": "unless-stopped",
            "entrypoint": ["node", "dist/index.js"],
            "command": ["gateway", "--bind", "lan", "--port", "18789"],
            "environment": environment, "ports": published,
            "extra_hosts": ["host.docker.internal:host-gateway"],
            "volumes": [
                {"type": "bind", "source": literal(config["project_dir"]),
                 "target": "/workspace/project", "bind": {"create_host_path": False}},
                {"type": "bind", "source": literal(BOOTSTRAP),
                 "target": "/opt/project-kit", "read_only": True},
                {"type": "volume", "source": "state", "target": "/home/node/.openclaw"},
                {"type": "volume", "source": "auth", "target": "/home/node/.config/openclaw"},
                {"type": "volume", "source": "cache", "target": "/home/node/.cache"},
            ],
        }},
        "volumes": {"state": {}, "auth": {}, "cache": {}},
    }


def config_patch(config):
    port = config["gateway_port"]
    return {
        "gateway": {"mode": "local", "bind": "lan", "port": 18789,
                    "auth": {"mode": "token", "token": "$" + "{OPENCLAW_GATEWAY_TOKEN}"},
                    "controlUi": {"allowedOrigins": [
                        f"http://localhost:{port}", f"http://127.0.0.1:{port}"]}},
        "agents": {"entries": {"main": {"workspace": "/home/node/.openclaw/workspace"}}},
        "tools": {"profile": "coding", "exec": {"host": "gateway"}},
        "memory": {"search": {"provider": "local", "fallback": "none",
                              "local": {"modelPath": EMBEDDING}}},
    }


def prepare(config):
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    identity_path = RUNTIME / "identity.json"
    if identity_path.exists():
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    else:
        uid, gid = local_identity()
        identity = {"instance": f"ocp-{config['name']}-{secrets.token_hex(4)}",
                    "uid": uid, "gid": gid}
        write_json(identity_path, identity)
    if (identity["uid"], identity["gid"]) != local_identity():
        raise ValueError("UID/GID mudou. Use um kit novo neste host e restaure o backup do projeto.")
    env_path = RUNTIME / ".env"
    if not env_path.exists():
        write_atomic(env_path, "OPENCLAW_GATEWAY_TOKEN=" + secrets.token_hex(32) + "\n")
    write_json(RUNTIME / "compose.json", compose_document(
        config, identity["instance"], identity["uid"], identity["gid"]))
    BOOTSTRAP.mkdir(mode=0o755, exist_ok=True)
    write_atomic(BOOTSTRAP / "patch.json", json.dumps(config_patch(config), indent=2), 0o644)
    stack_document = stack_config.document_for(config)
    write_atomic(BOOTSTRAP / "stack.json", json.dumps(stack_document, ensure_ascii=False, indent=2) + "\n", 0o644)
    context = (
        f"# Projeto {config['name']}\n\n"
        "A stack já está definida no arquivo JSON /opt/project-kit/stack.json. "
        "Leia esse arquivo antes de decidir tecnologias ou iniciar o desenvolvimento. "
        "Há também uma cópia stack.json no workspace de cada agente. "
        "Não peça ao usuário uma descrição textual da stack: ela já foi configurada. "
        "Pergunte apenas sobre requisitos ausentes ou conflitos concretos com o repositório. "
        "O arquivo editável de origem é stack.json na pasta do kit no host "
        "(ou o caminho indicado por stack_file em project.json). "
        "As cópias internas são geradas pelo setup.\n\n"
        "O código está em /workspace/project, compartilhado em leitura e escrita com o host. "
        "Execute comandos de desenvolvimento nessa pasta e leia seu AGENTS.md e manifests. "
        "Preserve a stack e o lockfile de um repositório existente; não migre tecnologias automaticamente. "
        "Guarde memórias no workspace do agente.\n\n"
        "As tecnologias estão em technologies, a organização em structure e os critérios em quality. "
        "development define comandos, variáveis e portas. Dentro do container, o servidor deve "
        "escutar em 0.0.0.0; o usuário acessa as portas publicadas em localhost. "
        "Os comandos pressupõem os manifests correspondentes: para uma pasta vazia, primeiro "
        "crie o projeto conforme o JSON e os requisitos do usuário.\n"
    )
    write_atomic(BOOTSTRAP / "context.md", context + features.context(config), 0o644)
    write_atomic(BOOTSTRAP / "agents.json", json.dumps(config["agents"], ensure_ascii=False), 0o644)
    write_atomic(BOOTSTRAP / "integrations.json", json.dumps(config["integrations"]), 0o644)
    for filename in ("seed.mjs", "verify-integrations.mjs", "runtime-config-preload.mjs"):
        shutil.copyfile(ROOT / filename, BOOTSTRAP / filename)
        os.chmod(BOOTSTRAP / filename, 0o644)
    return identity


def gateway_token():
    path = RUNTIME / ".env"
    if not path.exists():
        raise ValueError("Token do Gateway ausente. Execute python3 setup.py primeiro.")
    token_line = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"OPENCLAW_GATEWAY_TOKEN=[a-f0-9]{64}", token_line):
        raise ValueError("Arquivo .runtime/.env inválido.")
    return token_line.split("=", 1)[1]


def show_access():
    if not CONFIG.exists() or not (RUNTIME / "identity.json").exists():
        raise ValueError("Execute python3 setup.py primeiro.")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    port = port_number(config.get("gateway_port", 18889))
    token = gateway_token()
    print(f"Painel: http://localhost:{port}")
    print("Token do Gateway: " + token)
    print("Abra o painel e cole o token nas configurações de conexão.")
    print("Se o navegador solicitar pareamento, execute:")
    print("  python3 setup.py cli devices list")
    print("  python3 setup.py cli devices approve ID_DA_SOLICITACAO")


class Project:
    def __init__(self, identity):
        self.identity = identity
        self.base = ["docker", "compose", "--project-directory", str(ROOT),
                     "--env-file", str(RUNTIME / ".env"), "-p", identity["instance"],
                     "-f", str(RUNTIME / "compose.json")]
        self.env = os.environ.copy()
        self.env["OPENCLAW_GATEWAY_TOKEN"] = gateway_token()
        # Never inherit unrelated host credentials. Disabled integrations receive no runtime env.
        self.secrets = features.read_secrets(RUNTIME)
        for key in features.SECRET_KEYS.values():
            self.env.pop(key, None)
        self.env.update(self.secrets)

    def compose(self, *args, capture=False):
        result = subprocess.run(self.base + list(args), cwd=ROOT, env=self.env,
                                check=True, text=True, encoding="utf-8",
                                stdout=subprocess.PIPE if capture else None)
        return result.stdout.strip() if capture else ""

    def offline(self, *args, capture=False):
        # An explicit Gateway port forces CLI reads to use RPC even when stopped.
        prefix = ["run", "--rm", "--no-deps", "-e", "OPENCLAW_GATEWAY_PORT="]
        if args[:2] == ("config", "patch"):
            prefix.extend(["-e", "NODE_OPTIONS=--import=/opt/project-kit/runtime-config-preload.mjs"])
        for key in self.secrets:
            prefix.extend(["-e", key])
        if capture or not sys.stdin.isatty():
            prefix.append("-T")
        return self.compose(*prefix, "openclaw", *args, capture=capture)

    def command(self, executable, *args, capture=False):
        prefix = ["run", "--rm", "--no-deps"]
        if capture or not sys.stdin.isatty():
            prefix.append("-T")
        for key in self.secrets:
            prefix.extend(["-e", key])
        return self.compose(*prefix, "--entrypoint", executable, "openclaw", *args, capture=capture)

    def node(self, code):
        return self.command("node", "-e", code, capture=True)

    def stored_config(self):
        code = """
const fs = require('fs');
const p = '/home/node/.openclaw/openclaw.json';
if (!fs.existsSync(p)) { console.log('{}'); }
else {
  const c = JSON.parse(fs.readFileSync(p, 'utf8'));
  console.log(JSON.stringify({
    agents: c.agents,
    llamaInstalled: !!c.plugins?.entries?.['llama-cpp'],
    managedMemory: !!c.models?.providers?.['llama-cpp']?.localService,
    localChatModels: c.models?.providers?.['llama-cpp']?.models ?? [],
    openaiModels: c.models?.providers?.openai?.models ?? [],
    ollama: !!c.models?.providers?.ollama
  }));
}
"""
        return json.loads(self.node(code))


def cloud_model_present(config):
    models = [config.get("agents", {}).get("defaults", {}).get("model")]
    models += [a.get("model") for a in config.get("agents", {}).get("entries", {}).values()]
    selected = []
    for model in models:
        if isinstance(model, str):
            selected.append(model)
        elif isinstance(model, dict) and model.get("primary"):
            selected.append(model["primary"])
    return bool(selected) and all(not m.startswith(("ollama/", "llama-cpp/")) for m in selected)


def check_ports(config):
    for port in [config["gateway_port"]] + [p["host"] for p in config.get("ports", [])]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as error:
                raise ValueError(f"Porta {port} ocupada. Ajuste gateway_port em project.json ou development.ports em stack.json.") from error


def verify_mount(config, project):
    fd, filename = tempfile.mkstemp(prefix=".openclaw-mount-check-", dir=config["project_dir"])
    marker = secrets.token_hex(16)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(marker)
        container_path = "/workspace/project/" + Path(filename).name
        code = (
            "const fs = require('fs');"
            f"const p = {json.dumps(container_path)};"
            f"if (fs.readFileSync(p, 'utf8') !== {json.dumps(marker)}) "
            "{ throw new Error('Montagem aponta para outra pasta'); }"
            f"fs.writeFileSync(p, {json.dumps(marker + '-container')});"
        )
        project.node(code)
        if Path(filename).read_text(encoding="utf-8") != marker + "-container":
            raise ValueError("A escrita no contêiner não apareceu no host.")
        print("Montagem verificada em leitura e escrita entre host e contêiner.")
    finally:
        Path(filename).unlink(missing_ok=True)


def setup(config, project, edit_models=False):
    print("\nConstruindo ferramentas da stack " + config["stack"])
    project.compose("config", "--quiet")
    project.compose("build", "openclaw")
    project.compose("stop", "openclaw")
    check_ports(config)
    verify_mount(config, project)
    state = project.stored_config()
    if not cloud_model_present(state):
        print("\nEscolha seu provedor de nuvem para as conversas e autentique sua própria conta.")
        print("A memória EmbeddingGemma será configurada na etapa seguinte.")
        project.offline("onboard", "--classic", "--flow", "quickstart", "--mode", "local",
                        "--agent-name", "main", "--no-install-daemon", "--skip-health",
                        "--skip-channels", "--gateway-bind", "lan",
                        "--gateway-auth", "token", "--gateway-token-ref-env",
                        "OPENCLAW_GATEWAY_TOKEN")
        state = project.stored_config()
    if not cloud_model_present(state):
        raise ValueError("Selecione um modelo de nuvem no onboarding e execute setup novamente.")
    if state.get("ollama") or state.get("localChatModels"):
        raise ValueError("Esta instalação possui rotas locais de conversa. Revise-as com o comando cli.")
    features.select_models(sys.modules[__name__], config, project, force=edit_models)
    state = project.stored_config()
    # Refuse local chat defaults or fallbacks introduced by any interactive wizard.
    for agent in [state.get("agents", {}).get("defaults", {})] + list(state.get("agents", {}).get("entries", {}).values()):
        model = agent.get("model")
        if isinstance(model, str):
            features.remote_ref(model)
        elif isinstance(model, dict):
            for ref in [model.get("primary")] + model.get("fallbacks", []):
                if ref:
                    features.remote_ref(ref)
    if not state.get("llamaInstalled"):
        project.offline("plugins", "install",
                        "@openclaw/llama-cpp-provider@2026.11.3", "--pin", "--accept-capabilities")
    project.offline("plugins", "enable", "llama-cpp", "--accept-capabilities")
    project.offline("config", "patch", "--file", "/opt/project-kit/patch.json")
    if not state.get("managedMemory"):
        print("\nInstalando llama.cpp e EmbeddingGemma 300M para memória local (~330 MB de pesos).")
        project.offline("onboard", "--non-interactive", "--accept-risk",
                        "--auth-choice", "llama-cpp", "--llama-cpp-embedding-only",
                        "--no-install-daemon", "--skip-health")
    features.create_agents(config, project, project.stored_config())
    if config["integrations"]["telegram"].get("enabled"):
        project.offline("channels", "add", "--channel", "telegram", "--use-env")
    write_atomic(BOOTSTRAP / "features.json", json.dumps(features.patch(config, project.stored_config()), indent=2), 0o644)
    project.offline("config", "patch", "--file", "/opt/project-kit/features.json")
    if config["integrations"]["telegram"].get("enabled"):
        project.offline("agents", "bind", "--agent", "main", "--bind", "telegram:default")
    # Refresh the manifest after the model wizard changed project.json.
    write_atomic(BOOTSTRAP / "agents.json", json.dumps(config["agents"], ensure_ascii=False), 0o644)
    project.command("node", "/opt/project-kit/seed.mjs")
    project.offline("config", "validate")
    verify_connections(config, project)
    for agent in config["agents"]:
        project.offline("memory", "index", "--agent", agent["id"])
        project.offline("memory", "status", "--deep", "--agent", agent["id"])
    project.compose("up", "-d", "--wait", "--wait-timeout", "180", "openclaw")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{config['gateway_port']}/healthz", timeout=10) as response:
        if response.status != 200:
            raise ValueError("Healthcheck pelo localhost falhou.")
    print(f"\nPainel pronto em http://localhost:{config['gateway_port']}")
    print("Execute python3 setup.py acesso para consultar o endereço e o token do painel.")
    print("Pasta compartilhada: " + config["project_dir"])
    print("Dependências do projeto: python3 setup.py install")
    print("Aplicação: python3 setup.py dev NOME")
    print("Use python3 setup.py status para conferir contêiner e portas.")
    print("Reconfigurar: python3 setup.py integrations | models | credentials")
    print("Distribuir uma cópia limpa: python3 setup.py package")


def verify_connections(config, project):
    features.verify_models(config, project)
    project.command("node", "/opt/project-kit/verify-integrations.mjs")
    if config["integrations"]["github"].get("enabled"):
        # A read-only call verifies the installed CLI as well as repository access.
        project.command("gh", "repo", "view", config["integrations"]["github"]["repository"],
                        "--json", "nameWithOwner", capture=True)
        print("GitHub CLI: acesso ao repositório confirmado.")
    if config["integrations"]["linear"].get("enabled"):
        project.offline("mcp", "probe", "linear")


DISTRIBUTION_FILES = [
    "AGENTS.md",
    "Dockerfile", ".dockerignore", ".gitignore", "project.example.json",
    "setup.py", "features.py", "seed.mjs", "verify-integrations.mjs",
    "README.md", "test_setup.py", "test_feature_scripts.mjs",
    "stack_config.py", "stack.example.json", "stack.schema.json", "test_stack_config.py",
    "runtime-config-preload.mjs",
]


def package():
    destination = ROOT / "dist" / "openclaw-projeto-container.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in DISTRIBUTION_FILES:
            archive.write(ROOT / filename, "openclaw-projeto/" + filename)
    print("Pacote limpo criado em " + str(destination))
    return destination


@contextlib.contextmanager
def exclusive():
    lock = ROOT / ".kit.lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError("Outro comando do kit está ativo. Se foi interrompido à força, remova .kit.lock.") from error
    try:
        yield
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="setup",
                        choices=["setup", "configure", "status", "logs", "stop", "start",
                                 "shell", "install", "dev", "cli", "integrations",
                                 "models", "credentials", "check", "package", "acesso"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "acesso":
        show_access()
        return
    if args.action == "package":
        with exclusive():
            package()
        return
    if sys.platform == "win32":
        raise ValueError("Abra o terminal Ubuntu/WSL2 e execute python3 setup.py.")
    if args.action == "configure":
        with exclusive():
            configure()
        return
    if args.action in {"setup", "integrations", "models", "credentials"}:
        with exclusive():
            config = configure()
            if args.action == "integrations":
                features.configure(config, ask)
                write_json(CONFIG, validate(config))
            features.collect_secrets(config, RUNTIME, write_json, rotate=args.action == "credentials")
            if shutil.which("docker") is None:
                raise ValueError("Instale Docker com Compose v2 e habilite o acesso neste terminal.")
            subprocess.run(["docker", "compose", "version"], check=True)
            subprocess.run(["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"], check=True)
            project = Project(prepare(config))
            setup(config, project, edit_models=args.action == "models")
        return
    if not (RUNTIME / "identity.json").exists():
        raise ValueError("Execute python3 setup.py primeiro.")
    config = validate(json.loads(CONFIG.read_text(encoding="utf-8")))
    identity = json.loads((RUNTIME / "identity.json").read_text(encoding="utf-8"))
    project = Project(identity)
    if args.action == "check":
        with exclusive():
            running = bool(project.compose("ps", "--status", "running", "-q", "openclaw", capture=True))
            project.compose("stop", "openclaw")
            try:
                verify_connections(config, project)
            finally:
                if running:
                    project.compose("up", "-d", "--wait", "--wait-timeout", "180", "openclaw")
    elif args.action == "status":
        project.compose("ps")
    elif args.action == "logs":
        project.compose("logs", "--tail=100", "-f", "openclaw")
    elif args.action == "stop":
        project.compose("stop", "openclaw")
    elif args.action == "start":
        if not project.compose("ps", "--status", "running", "-q", "openclaw", capture=True):
            check_ports(config)
        project.compose("up", "-d", "--wait", "--wait-timeout", "180", "openclaw")
    elif args.action == "shell":
        project.compose("exec", "-w", "/workspace/project", "openclaw", "bash")
    elif args.action == "cli":
        if not args.arguments:
            raise ValueError("Informe o comando OpenClaw, por exemplo cli devices list.")
        if project.compose("ps", "--status", "running", "-q", "openclaw", capture=True):
            project.compose("exec", "openclaw", "node", "dist/index.js", *args.arguments)
        else:
            project.offline(*args.arguments)
    else:
        if args.action == "install":
            command = config.get("install_command")
        else:
            choices = config.get("dev_commands", {})
            name = args.arguments[0] if args.arguments else "app"
            command = choices.get(name)
            if not command:
                raise ValueError("Escolha um comando em development.dev_commands de stack.json: " + ", ".join(choices))
        if not command:
            raise ValueError("Preencha development.install_command em stack.json.")
        project.compose("exec", "-w", "/workspace/project", "openclaw", "bash", "-lc", command)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"\nFalha: {error}", file=sys.stderr)
        print("Corrija o item indicado e execute novamente o comando.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrompido. Você pode repetir o setup.", file=sys.stderr)
        sys.exit(130)
