import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { seedWorkspace } from "./seed.mjs";
import { verifyIntegrations } from "./verify-integrations.mjs";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "ocp-feature-tests-"));
try {
  const workspace = path.join(root, "workspace");
  fs.mkdirSync(workspace);
  fs.writeFileSync(path.join(workspace, "AGENTS.md"), "Instrução existente.\n");
  seedWorkspace(workspace, "Stack inicial", "Arquiteto");
  seedWorkspace(workspace, "Stack nova", "Revisor", {schema_version:1, technologies:{frontend:"Next.js"}});
  assert.equal(JSON.parse(fs.readFileSync(path.join(workspace,"stack.json"),"utf8")).technologies.frontend,"Next.js");
  const instructions = fs.readFileSync(path.join(workspace, "AGENTS.md"), "utf8");
  assert.ok(instructions.includes("Instrução existente."));
  assert.ok(instructions.includes("Stack nova"));
  assert.ok(instructions.includes("Revisor"));
  assert.ok(!instructions.includes("Stack inicial"));
  assert.equal(instructions.split("<!-- project-kit:start -->").length, 2);
  assert.ok(fs.readFileSync(path.join(workspace, "memory", "project-kit.md"), "utf8").includes("Revisor"));

  seedWorkspace(workspace, "Projeto", "Pesquisa", null, {"AGENTS.md":"Função importada", "SOUL.md":"Identidade importada"});
  assert.ok(fs.readFileSync(path.join(workspace, "AGENTS.md.pre-import"), "utf8").includes("Instrução existente."));
  assert.ok(fs.readFileSync(path.join(workspace, "AGENTS.md"), "utf8").includes("Função importada"));
  fs.writeFileSync(path.join(workspace, "SOUL.md"), "Edição posterior do usuário");
  seedWorkspace(workspace, "Projeto atualizado", "Pesquisa", null, {"SOUL.md":"Identidade importada"});
  assert.equal(fs.readFileSync(path.join(workspace, "SOUL.md"), "utf8"), "Edição posterior do usuário");
  assert.throws(()=>seedWorkspace(workspace,"","",null,{"../auth.json":"invalid"}),/inválido/);

  const env = {GH_TOKEN:"FAKE_GH_SECRET", LINEAR_API_KEY:"FAKE_LINEAR_SECRET", TELEGRAM_BOT_TOKEN:"123:FAKE_TELEGRAM_SECRET"};
  const config = {github:{enabled:true, repository:"example/repo"}, linear:{enabled:true}, telegram:{enabled:true}};
  const calls = [], logs = [];
  const response = data => ({ok:true,status:200,json:async()=>data});
  const mockFetch = async (url, options) => {
    calls.push({url, options});
    if (url.endsWith("/getMe")) return response({ok:true,result:{is_bot:true}});
    if (url.endsWith("/getWebhookInfo")) return response({ok:true,result:{url:""}});
    return response({full_name:"example/repo"});
  };
  await verifyIntegrations(config, env, mockFetch, text=>logs.push(text));
  assert.equal(calls.length, 3);
  assert.ok(calls.every(c=>c.options.redirect==="error" && !c.options.method));
  assert.ok(!logs.join().includes("FAKE_"));

  await assert.rejects(verifyIntegrations({telegram:{enabled:true}},env,async(url)=>
    response(url.endsWith("/getMe") ? {ok:true,result:{is_bot:true}} : {ok:true,result:{url:"https://existing.bot"}}),()=>{}), /bot separado/);
  await assert.rejects(verifyIntegrations({github:config.github},env,async()=>({ok:false,status:401}),()=>{}), /HTTP 401/);
  await assert.rejects(verifyIntegrations({github:config.github},env,async()=>{throw Error("FAKE_GH_SECRET");},()=>{}),
    error=>!error.message.includes("FAKE_GH_SECRET") && error.message.includes("conexão"));
  await assert.rejects(verifyIntegrations({github:config.github},env,async()=>response({full_name:"other/repo"}),()=>{}), /não corresponde/);
  await verifyIntegrations({}, {}, async()=>{throw Error("Disabled integrations must not connect");},()=>{});
  console.log("8 verificações JavaScript passaram: contexto, importação, acesso, bot, erros e integrações desabilitadas.");
} finally {
  fs.rmSync(root, {recursive:true,force:true});
}
