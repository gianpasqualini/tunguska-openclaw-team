"""Regressões de stack declarativa, sem Docker ou contas externas."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import setup as kit
import stack_config


class StackTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.TemporaryDirectory()
        self.addCleanup(self.base.cleanup)
        root = Path(self.base.name)
        self.kit = root / "kit"
        self.kit.mkdir()
        self.code = root / "code"
        self.code.mkdir()
        source = Path(__file__).parent
        self.reference = json.loads((source / "stack.example.json").read_text(encoding="utf-8"))
        for name in ("stack.example.json", "seed.mjs", "verify-integrations.mjs", "runtime-config-preload.mjs"):
            (self.kit / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
        for setting, value in (
            ("ROOT", self.kit), ("CONFIG", self.kit / "project.json"),
            ("RUNTIME", self.kit / ".runtime"), ("BOOTSTRAP", self.kit / ".runtime" / "bootstrap"),
        ):
            p = patch.object(kit, setting, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(Path, "home", return_value=root / "fake-home")
        p.start()
        self.addCleanup(p.stop)

    def config(self):
        kit.write_json(self.kit / "stack.json", self.reference)
        return {"name":"novo","project_dir":str(self.code),"gateway_port":18889,"stack_file":"stack.json","kit_version":3}

    def test_first_setup_never_asks_stack_or_commands(self):
        prompts = []
        answers = iter(["novo", str(self.code), "18889", "n", "n", "n", "n"])
        def ask(label, default=""):
            prompts.append(label)
            return next(answers)
        with patch.object(kit, "ask", side_effect=ask):
            config = kit.configure()
        self.assertEqual(config["stack"], "node")
        self.assertEqual(config["ports"], [{"host":3000,"container":3000}])
        self.assertFalse(any("stack" in p.lower() or "comando" in p.lower() or "apt" in p.lower() for p in prompts))
        saved = json.loads(kit.CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(saved["stack_file"], "stack.json")
        self.assertFalse(set(saved) & set(stack_config.DERIVED))

    def test_json_controls_runtime_ports_commands_and_agent_snapshot(self):
        config = self.config()
        self.reference["runtime"]["preset"] = "node-python"
        self.reference["development"]["ports"] = [{"host":15173,"container":5173}]
        self.reference["development"]["dev_commands"] = {"web":"custom-dev --host 0.0.0.0"}
        self.reference["technologies"] = {"frontend":{"framework":"Outra stack"}}
        kit.write_json(self.kit / "stack.json", self.reference)
        kit.validate(config)
        with patch.object(kit,"local_identity",return_value=(1001,1001)):
            kit.prepare(config)
        snapshot = json.loads((kit.BOOTSTRAP / "stack.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot, self.reference)
        compose = json.loads((kit.RUNTIME / "compose.json").read_text(encoding="utf-8"))
        service = compose["services"]["openclaw"]
        self.assertIn("python3", service["build"]["args"]["STACK_APT_PACKAGES"])
        self.assertEqual(service["ports"][1]["published"], "15173")
        self.assertEqual(config["dev_commands"]["web"], "custom-dev --host 0.0.0.0")
        self.assertIn("Não peça ao usuário uma descrição textual", (kit.BOOTSTRAP / "context.md").read_text(encoding="utf-8"))

    def test_legacy_migration_preserves_choices_and_existing_stack(self):
        legacy = {"name":"old","project_dir":str(self.code),"stack":"python",
                  "ports":[{"host":18000,"container":8000}], "environment":{"APP_MODE":"local"},
                  "dev_commands":{"api":"python app.py"},"install_command":"pip install -r requirements.txt","kit_version":2}
        kit.write_json(self.kit / "stack.json", self.reference)
        kit.write_json(kit.CONFIG, legacy)
        with patch.object(kit,"ask", side_effect=AssertionError("Do not prompt")):
            config = kit.configure()
        self.assertEqual(config["stack"],"python")
        self.assertEqual(config["stack_file"],"stack.legacy.json")
        self.assertEqual(config["ports"],legacy["ports"])
        self.assertEqual(config["_stack_document"]["technologies"],{})
        self.assertEqual(json.loads((self.kit/"stack.json").read_text(encoding="utf-8")),self.reference)
        self.assertEqual(json.loads((self.kit/"project.pre-stack-json.json").read_text(encoding="utf-8")),legacy)

    def test_example_project_creates_missing_default_stack_without_prompt(self):
        config = self.config()
        (self.kit/"stack.json").unlink()
        kit.write_json(kit.CONFIG,config)
        with patch.object(kit,"ask",side_effect=AssertionError("Do not prompt")):
            result = kit.configure()
        self.assertEqual(result["_stack_document"], self.reference)

    def test_bad_json_or_dangerous_settings_fail_before_docker(self):
        config = self.config()
        (self.kit/"stack.json").write_text('{"bad":',encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"JSON inválido"):
            kit.validate(config)
        for change in (
            lambda d:d["runtime"].update(preset="unknown"),
            lambda d:d["development"].update(ports=[{"host":18889,"container":3000}]),
            lambda d:d["development"].update(environment={"GH_TOKEN":"private"}),
        ):
            doc = copy.deepcopy(self.reference)
            change(doc)
            kit.write_json(self.kit/"stack.json",doc)
            with self.assertRaises(ValueError):
                kit.validate(config)
        with self.assertRaises(ValueError):
            stack_config.config_path(self.kit,"../outside.json")

    def test_resaving_project_does_not_duplicate_or_override_json_stack(self):
        config = self.config()
        kit.validate(config)
        config["models_configured"] = True
        kit.write_json(kit.CONFIG,config)
        saved=json.loads(kit.CONFIG.read_text(encoding="utf-8"))
        self.assertNotIn("ports",saved)
        self.assertNotIn("_stack_document",saved)
        self.reference["development"]["ports"]=[{"host":14000,"container":3000}]
        kit.write_json(self.kit/"stack.json",self.reference)
        kit.validate(saved)
        self.assertEqual(saved["ports"][0]["host"],14000)


if __name__ == "__main__":
    unittest.main()
