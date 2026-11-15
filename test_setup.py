"""Testes locais sem Docker e sem chamadas às contas externas."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import setup as kit
import features


class KitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "kit"
        self.code = base / "projeto espaço $ acao"
        self.root.mkdir()
        self.code.mkdir()
        self.runtime = self.root / ".runtime"
        self.bootstrap = self.runtime / "bootstrap"
        self.patches = [
            patch.object(kit, "ROOT", self.root),
            patch.object(kit, "CONFIG", self.root / "project.json"),
            patch.object(kit, "RUNTIME", self.runtime),
            patch.object(kit, "BOOTSTRAP", self.bootstrap),
            patch.object(kit, "local_identity", return_value=(1001, 1001)),
            patch.object(Path, "home", return_value=base / "test-home"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        for name in kit.DISTRIBUTION_FILES:
            (self.root / name).write_text("fixture\n", encoding="utf-8")
        self.config = kit.validate({
            "name": "teste", "project_dir": str(self.code), "stack": "node-python",
            "gateway_port": 18889, "ports": [{"host": 15173, "container": 5173}],
            "environment": {}, "kit_version": 2, "models_configured": True,
            "integrations": {
                "github": {"enabled": True, "repository": "example/repo"},
                "linear": {"enabled": True, "team": "Equipe", "project": "Novo", "access": "read-only"},
                "telegram": {"enabled": True, "allowed_user_ids": ["123456"]},
            },
            "agents": [
                {"id": "main", "role": "Coordene", "model": "", "fallbacks": []},
                {"id": "revisao", "role": "Revise", "model": "vendor/review", "fallbacks": ["vendor/backup"]},
            ],
        })
        kit.write_json(self.runtime / "secrets.json", {
            "GH_TOKEN": "FAKE_GH_SECRET", "LINEAR_API_KEY": "FAKE_LINEAR_SECRET",
            "TELEGRAM_BOT_TOKEN": "123:FAKE_TELEGRAM_SECRET",
        })

    def test_access_command_reads_existing_token_without_docker_or_project_folder(self):
        kit.prepare(self.config)
        kit.write_json(kit.CONFIG, {"gateway_port": 19999})
        token_before = (self.runtime / ".env").read_bytes()
        output = io.StringIO()
        with patch("sys.argv", ["setup.py", "acesso"]), patch("sys.stdout", output), \
             patch.object(kit.subprocess, "run", side_effect=AssertionError("Docker must not run")):
            kit.main()
        self.assertIn("http://localhost:19999", output.getvalue())
        self.assertIn(token_before.decode().strip().split("=", 1)[1], output.getvalue())
        self.assertIn("devices approve ID_DA_SOLICITACAO", output.getvalue())
        self.assertEqual((self.runtime / ".env").read_bytes(), token_before)

    def test_access_rejects_missing_or_invalid_state_without_disclosing_contents(self):
        with self.assertRaisesRegex(ValueError, "primeiro"):
            kit.show_access()
        kit.prepare(self.config)
        kit.write_json(kit.CONFIG, {"gateway_port": 18889})
        (self.runtime / ".env").unlink()
        with self.assertRaisesRegex(ValueError, "ausente"):
            kit.show_access()
        (self.runtime / ".env").write_text("PRIVATE_INVALID_CONTENT")
        output = io.StringIO()
        with patch("sys.stdout", output), self.assertRaisesRegex(ValueError, "inválido"):
            kit.show_access()
        self.assertEqual(output.getvalue(), "")

    def test_generated_files_have_no_secrets_and_localhost_only(self):
        first = kit.prepare(self.config)
        second = kit.prepare(self.config)
        self.assertEqual(first, second)
        document = json.loads((self.runtime / "compose.json").read_text())
        service = document["services"]["openclaw"]
        self.assertTrue(all(p["host_ip"] == "127.0.0.1" for p in service["ports"]))
        self.assertEqual(service["environment"]["GH_REPO"], "example/repo")
        self.assertIn("GH_TOKEN:?", service["environment"]["GH_TOKEN"])
        self.assertIn("$$", service["volumes"][0]["source"])
        self.assertNotIn("docker.sock", json.dumps(document))
        for file in [self.runtime / "compose.json", *self.bootstrap.iterdir()]:
            self.assertNotIn("FAKE_", file.read_text(encoding="utf-8"))
        self.assertTrue(all(v == {} for v in document["volumes"].values()))

    def test_project_env_overrides_foreign_tokens_and_never_uses_arguments(self):
        identity = kit.prepare(self.config)
        with patch.dict(os.environ, {"GH_TOKEN": "FOREIGN", "LINEAR_API_KEY": "FOREIGN"}):
            project = kit.Project(identity)
        self.assertEqual(project.env["GH_TOKEN"], "FAKE_GH_SECRET")
        with patch.object(project, "compose", return_value="") as command:
            project.offline("config", "validate")
            args = command.call_args.args
        self.assertIn("GH_TOKEN", args)
        self.assertNotIn("FAKE_GH_SECRET", repr(args))

    def test_disabling_integrations_removes_runtime_access_and_stale_config(self):
        for item in self.config["integrations"].values():
            item["enabled"] = False
        self.assertEqual(features.environment(self.config), {})
        delta = features.patch(self.config)
        self.assertIsNone(delta["mcp"]["servers"]["linear"])
        self.assertIsNone(delta["channels"]["telegram"])
        # Stored secrets remain available to offline migration while old config is loaded.
        identity = kit.prepare(self.config)
        self.assertEqual(kit.Project(identity).secrets["GH_TOKEN"], "FAKE_GH_SECRET")

    def test_agent_models_roles_delegation_and_memory_separation(self):
        delta = features.patch(self.config)
        agents = delta["agents"]["entries"]
        self.assertIsNone(agents["main"]["model"])
        self.assertEqual(agents["revisao"]["model"], {"primary": "vendor/review", "fallbacks": ["vendor/backup"]})
        self.assertEqual(agents["main"]["subagents"]["allowAgents"], ["revisao"])
        self.assertEqual(agents["revisao"]["subagents"]["allowAgents"], [])
        self.assertNotEqual(agents["main"]["workspace"], agents["revisao"]["workspace"])
        self.assertEqual(delta["session"]["dmScope"], "per-channel-peer")
        self.assertEqual(delta["channels"]["telegram"]["groupPolicy"], "disabled")
        self.assertTrue(delta["mcp"]["servers"]["linear"]["url"].endswith("/readonly"))

    def test_reject_unsafe_and_invalid_config(self):
        for mutate in [
            lambda c: c["agents"][0].update(model="ollama/qwen"),
            lambda c: c["agents"][0].update(fallbacks=["llama-cpp/chat"]),
            lambda c: c["agents"][1].update(id="main"),
            lambda c: c["agents"][1].update(id="../../outside"),
            lambda c: c["integrations"]["telegram"].update(allowed_user_ids=["*"]),
            lambda c: c["integrations"]["telegram"].update(allowed_user_ids=["-100123"]),
            lambda c: c["integrations"]["github"].update(repository="https://github.com/a/b"),
            lambda c: c["integrations"]["linear"].update(api_key="private"),
            lambda c: c["environment"].update(GH_TOKEN="private"),
            lambda c: c.update(extra_apt_packages=["curl;touch /tmp/bad"]),
            lambda c: c.update(project_dir=str(self.root)),
            lambda c: c.update(ports=[{"host":18889,"container":5173}]),
        ]:
            candidate = copy.deepcopy(self.config)
            mutate(candidate)
            with self.assertRaises(ValueError):
                kit.validate(candidate)

    def test_credentials_preserved_and_rotated_without_echo(self):
        with patch.object(features.sys.stdin, "isatty", return_value=True), \
             patch.object(features.getpass, "getpass", side_effect=["", "NEW_LINEAR", "123:NEW_TELEGRAM"]):
            features.collect_secrets(self.config, self.runtime, kit.write_json, rotate=True)
        saved = features.read_secrets(self.runtime)
        self.assertEqual(saved["GH_TOKEN"], "FAKE_GH_SECRET")
        self.assertEqual(saved["LINEAR_API_KEY"], "NEW_LINEAR")

    def test_imported_agents_preserve_identity_and_delegation_boundaries(self):
        config = copy.deepcopy(self.config)
        config["agents"][0].update(name="Chefia", identity={"name":"Chefia","emoji":"🦉"}, delegates=["revisao"])
        config["agents"].append({"id":"cobaia", "role":"Independente", "model":"", "fallbacks":[], "delegates":[],
                                 "workspace_files":{"SOUL.md":"Pesquisa"}})
        features.validate(config)
        entries = features.patch(config)["agents"]["entries"]
        self.assertEqual(entries["main"]["identity"]["name"], "Chefia")
        self.assertEqual(entries["main"]["subagents"]["allowAgents"], ["revisao"])
        self.assertEqual(entries["cobaia"]["subagents"]["allowAgents"], [])
        config["agents"][0]["delegates"] = ["cognifun-gabi"]
        with self.assertRaises(ValueError):
            features.validate(config)
        config["agents"][0]["delegates"] = []
        config["agents"][-1]["workspace_files"] = {"../auth.json":"invalid"}
        with self.assertRaises(ValueError):
            features.validate(config)

    def test_profile_bound_remote_model_keeps_local_model_restriction(self):
        ref = "openai/gpt-6-astra@openai:setup-test"
        self.assertEqual(features.remote_ref(ref), ref)
        for invalid in ["ollama/qwen@local:default", "openai/gpt@", "openai/gpt@profile with spaces"]:
            with self.assertRaises(ValueError):
                features.remote_ref(invalid)

    def test_model_wizard_uses_catalog_and_preserves_choice_on_retry(self):
        class CatalogProject:
            def offline(self, *args, **kwargs):
                if args[:2] == ("models", "list"):
                    return "vendor/review\nvendor/backup\nollama/qwen"
                return ""
        responses = iter(["n", "", "herdar", "vendor/review", "vendor/backup"])
        with patch.object(features.sys.stdin, "isatty", return_value=True), \
             patch.object(kit, "ask", side_effect=lambda *a: next(responses)):
            features.select_models(kit, self.config, CatalogProject(), force=True)
        self.assertTrue(self.config["models_configured"])
        self.assertEqual(self.config["agents"][1]["fallbacks"], ["vendor/backup"])
        with patch.object(kit, "ask", side_effect=AssertionError("must not repeat")):
            features.select_models(kit, self.config, CatalogProject())

    def test_clean_package_excludes_runtime_config_and_extra_files(self):
        kit.write_json(self.root / "project.json", {"secret": "NEVER_DISTRIBUTE"})
        (self.root / "extra-private.txt").write_text("NEVER_DISTRIBUTE")
        dest = kit.package()
        with zipfile.ZipFile(dest) as z:
            self.assertEqual(set(z.namelist()), {"openclaw-projeto/" + n for n in kit.DISTRIBUTION_FILES})
            self.assertFalse(any(b"NEVER_DISTRIBUTE" in z.read(n) for n in z.namelist()))

    def test_new_agents_not_recreated_on_retry(self):
        calls = []
        class Project:
            def offline(self, *args, **kwargs):
                calls.append(args)
        state = {"agents": {"entries": {"main": {}}}}
        features.create_agents(self.config, Project(), state)
        self.assertEqual(calls[0][:3], ("agents", "add", "revisao"))
        calls.clear()
        state["agents"]["entries"]["revisao"] = {}
        features.create_agents(self.config, Project(), state)
        self.assertEqual(calls, [])

    def test_fresh_install_uses_saved_team_and_preserves_existing_agents(self):
        config = features.configure({}, lambda label, default="": default)
        by_id = {a["id"]: a for a in config["agents"]}
        terra = {"arquitetura", "frontend", "backend-ai", "qualidade", "devops"}
        astra = {"main", "produto", "ux", "cobaia"}
        self.assertEqual(set(by_id), terra | astra)
        for aid, agent in by_id.items():
            self.assertEqual(agent["model"], "openai/gpt-6.1-terra" if aid in terra else "openai/gpt-6-astra")
            self.assertEqual(agent["fallbacks"], [])
            self.assertIn("SOUL.md", agent["workspace_files"])
        self.assertNotIn("cobaia", by_id["main"]["delegates"])
        self.assertTrue(config["models_configured"])
        previous_model = {"id": "another-model", "name": "Preserve me"}
        delta = features.patch(config, {"openaiModels": [previous_model]})
        provider = delta["models"]["providers"]["openai"]
        self.assertNotIn("api", provider)
        self.assertNotIn("baseUrl", provider)
        self.assertEqual(provider["models"][0], previous_model)
        self.assertEqual(provider["models"][1]["api"], "openai-chatgpt-responses")
        existing = copy.deepcopy(self.config["agents"])
        features.configure(self.config, lambda label, default="": default)
        self.assertEqual(self.config["agents"], existing)

    def test_setup_checks_before_start_and_does_not_reonboard(self):
        kit.prepare(self.config)
        calls = []
        state = {"agents": {"defaults": {"model": "vendor/primary"}, "entries": {"main": {}, "revisao": {}}},
                 "llamaInstalled": True, "managedMemory": True}
        class Project:
            def compose(self, *args, **kwargs):
                calls.append(("compose", *args))
                return ""
            def stored_config(self):
                return state
            def offline(self, *args, **kwargs):
                calls.append(("offline", *args))
                return ""
            def command(self, *args, **kwargs):
                calls.append(("command", *args))
                return ""
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Opener:
            def open(self, *args, **kwargs): return Response()
        with patch.object(kit, "check_ports"), patch.object(kit, "verify_mount"), \
             patch.object(kit.urllib.request, "build_opener", return_value=Opener()):
            kit.setup(self.config, Project())
        self.assertFalse(any(c[1:2] == ("onboard",) for c in calls))
        up = next(i for i,c in enumerate(calls) if c[:2] == ("compose","up"))
        probe = next(i for i,c in enumerate(calls) if c[:3] == ("offline","mcp","probe"))
        self.assertLess(probe, up)
        for aid in ("main", "revisao"):
            self.assertIn(("offline", "memory", "status", "--deep", "--agent", aid), calls)

    def test_bad_model_auth_stops_setup_before_gateway(self):
        kit.prepare(self.config)
        calls = []
        class Project:
            def compose(self, *args, **kwargs):
                calls.append(args)
            def stored_config(self):
                return {"agents":{"defaults":{"model":"vendor/primary"},"entries":{"main":{},"revisao":{}}},
                        "llamaInstalled": True, "managedMemory": True}
            def offline(self, *args, **kwargs):
                if args[:2] == ("models", "status"):
                    raise subprocess.CalledProcessError(1, ["openclaw"])
                return ""
            def command(self, *args, **kwargs): return ""
        with patch.object(kit, "check_ports"), patch.object(kit, "verify_mount"), \
             self.assertRaisesRegex(ValueError, "prontidão"):
            kit.setup(self.config, Project())
        self.assertFalse(any(c and c[0] == "up" for c in calls))


if __name__ == "__main__":
    unittest.main()
