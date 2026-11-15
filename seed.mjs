import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function seedWorkspace(workspace, context, role, stack = null, templates = {}) {
  const instructions = path.join(workspace, "AGENTS.md");
  const start = "<!-- project-kit:start -->";
  const end = "<!-- project-kit:end -->";
  fs.mkdirSync(path.join(workspace, "memory"), { recursive: true });
  const allowed = new Set(["AGENTS.md", "SOUL.md", "IDENTITY.md", "TEAM_PLAYBOOK.md"]);
  for (const [name, content] of Object.entries(templates)) {
    if (!allowed.has(name) || typeof content !== "string") throw new Error("Arquivo de instruções inválido.");
  }
  const marker = path.join(workspace, ".project-kit-imported");
  if (Object.keys(templates).length && !fs.existsSync(marker)) {
    for (const [name, content] of Object.entries(templates)) {
      const target = path.join(workspace, name);
      if (fs.existsSync(target) && !fs.existsSync(target + ".pre-import")) fs.copyFileSync(target, target + ".pre-import");
      fs.writeFileSync(target, content, { mode: 0o600 });
    }
    fs.writeFileSync(marker, "Imported agent instructions; subsequent setup preserves edits.\n", { mode: 0o600 });
  }
  let previous = fs.existsSync(instructions) ? fs.readFileSync(instructions, "utf8") : "";
  const startAt = previous.indexOf(start);
  const endAt = previous.indexOf(end);
  const block = start + "\n" + context + "\n## Sua função\n" + role + "\n" + end;
  if (startAt >= 0 && endAt >= startAt) {
    previous = previous.slice(0, startAt) + block + previous.slice(endAt + end.length);
  } else {
    previous = previous.trimEnd() + "\n\n" + block + "\n";
  }
  fs.writeFileSync(instructions, previous);
  if (stack !== null) fs.writeFileSync(path.join(workspace, "stack.json"), JSON.stringify(stack, null, 2) + "\n");
  fs.writeFileSync(path.join(workspace, "memory", "project-kit.md"), context + "\nSua função: " + role + "\n");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const context = fs.readFileSync("/opt/project-kit/context.md", "utf8");
  const stack = JSON.parse(fs.readFileSync("/opt/project-kit/stack.json", "utf8"));
  const agents = JSON.parse(fs.readFileSync("/opt/project-kit/agents.json", "utf8"));
  for (const agent of agents) {
    if (!/^[a-z][a-z0-9-]{0,39}$/.test(agent.id)) throw new Error("ID de agente inválido.");
    const workspace = "/home/node/.openclaw/" + (agent.id === "main" ? "workspace" : "workspace-" + agent.id);
    seedWorkspace(workspace, context, agent.role, stack, agent.workspace_files ?? {});
  }
  console.log("Contexto da stack, integrações e funções atualizado nos workspaces.");
}
