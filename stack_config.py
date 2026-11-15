"""Stack declarativa do projeto. O documento é consumido pelo kit e pelos agentes."""
import copy
import json
from pathlib import Path

DERIVED = ("stack", "extra_apt_packages", "ports", "install_command", "dev_commands", "environment", "_stack_document")


def read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido em {path.name}, linha {error.lineno}, coluna {error.colno}.") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} deve conter um objeto JSON.")
    return value


def validate(document):
    if document.get("schema_version") != 1 or isinstance(document.get("schema_version"), bool):
        raise ValueError("stack.json: schema_version deve ser 1.")
    if not isinstance(document.get("name"), str) or not document["name"].strip():
        raise ValueError("stack.json: informe name.")
    for name in ("runtime", "technologies", "development"):
        if not isinstance(document.get(name), dict):
            raise ValueError(f"stack.json: {name} deve ser um objeto.")
    runtime = document["runtime"]
    if not isinstance(runtime.get("preset"), str):
        raise ValueError("stack.json: runtime.preset deve ser texto.")
    if not isinstance(runtime.get("extra_apt_packages", []), list):
        raise ValueError("stack.json: runtime.extra_apt_packages deve ser uma lista.")
    dev = document["development"]
    if not isinstance(dev.get("ports", []), list) or any(
        not isinstance(p, dict) or "host" not in p or "container" not in p for p in dev.get("ports", [])
    ):
        raise ValueError("stack.json: development.ports deve listar objetos host/container.")
    for name in ("environment", "dev_commands"):
        if not isinstance(dev.get(name, {}), dict):
            raise ValueError(f"stack.json: development.{name} deve ser um objeto.")
    # Existing kit validation checks reserved env keys, commands, package syntax and port conflicts.
    return document


def config_path(root, filename):
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("stack_file deve indicar um arquivo JSON relativo à pasta do kit.")
    target = (root / filename).resolve()
    if target.suffix.lower() != ".json" or root.resolve() not in target.parents:
        raise ValueError("stack_file deve ser um JSON dentro da pasta deste kit.")
    if ".runtime" in target.relative_to(root.resolve()).parts:
        raise ValueError("stack_file não pode apontar para arquivos internos de .runtime.")
    return target


def hydrate(config, root):
    if "stack_file" not in config:
        return config  # Compatibility for old in-memory/test callers.
    document = validate(read(config_path(root, config["stack_file"])))
    runtime, dev = document["runtime"], document["development"]
    config.update({
        "stack": runtime["preset"],
        "extra_apt_packages": runtime.get("extra_apt_packages", []),
        "ports": copy.deepcopy(dev.get("ports", [])),
        "install_command": dev.get("install_command", ""),
        "dev_commands": copy.deepcopy(dev.get("dev_commands", {})),
        "environment": copy.deepcopy(dev.get("environment", {})),
        "_stack_document": copy.deepcopy(document),
    })
    return config


def project_fields(config):
    return {key: value for key, value in config.items() if key not in DERIVED}


def document_for(config):
    if "_stack_document" in config:
        return config["_stack_document"]
    # Legacy migration preserves settings without inventing application technologies.
    return {
        "schema_version": 1, "name": "Stack migrada do project.json",
        "runtime": {"preset": config["stack"], "extra_apt_packages": config.get("extra_apt_packages", [])},
        "technologies": {},
        "development": {key: copy.deepcopy(config.get(key, default)) for key, default in (
            ("ports", []), ("install_command", ""), ("dev_commands", {}), ("environment", {}))},
    }


def ensure(kit, config=None):
    if config is not None and "stack_file" in config:
        filename = config["stack_file"]
        destination = config_path(kit.ROOT, filename)
        if not destination.exists() and filename == "stack.json":
            kit.write_json(destination, read(kit.ROOT / "stack.example.json"))
        return filename
    if config is not None:
        filename = "stack.json" if not (kit.ROOT / "stack.json").exists() else "stack.legacy.json"
        destination = kit.ROOT / filename
        if destination.exists():
            raise ValueError("stack.legacy.json já existe. Defina stack_file em project.json para escolher o arquivo.")
        backup = kit.ROOT / "project.pre-stack-json.json"
        if not backup.exists():
            kit.write_json(backup, config)
        kit.write_json(destination, document_for(config))
        print("Stack anterior preservada em " + filename + ".")
    else:
        filename = "stack.json"
        destination = kit.ROOT / filename
        if not destination.exists():
            kit.write_json(destination, read(kit.ROOT / "stack.example.json"))
        print("Stack definida em " + str(destination) + ". Edite esse JSON para personalizar.")
    return filename
