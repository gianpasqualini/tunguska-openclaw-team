import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

async function requestJson(fetcher, name, url, options = {}) {
  let response;
  try {
    response = await fetcher(url, { ...options, redirect: "error", signal: AbortSignal.timeout(20000) });
  } catch {
    throw new Error(name + ": falha de conexão, redirecionamento recusado ou timeout.");
  }
  if (!response.ok) throw new Error(name + ": acesso recusado ou indisponível (HTTP " + response.status + ").");
  try { return await response.json(); }
  catch { throw new Error(name + ": resposta inválida."); }
}

export async function verifyIntegrations(config, env, fetcher = fetch, log = console.log) {
  if (config.github?.enabled) {
    const repo = config.github.repository;
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) throw new Error("Repositório inválido.");
    if (!env.GH_TOKEN) throw new Error("GitHub: credencial ausente.");
    const data = await requestJson(fetcher, "GitHub", "https://api.github.com/repos/" + repo, {
      headers: { Authorization: "Bearer " + env.GH_TOKEN, Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "openclaw-project-kit" },
    });
    if (!data.full_name || data.full_name.toLowerCase() !== repo.toLowerCase()) {
      throw new Error("GitHub: o repositório retornado não corresponde ao configurado.");
    }
    log("GitHub: repositório acessível. Permissões de escrita dependem do token.");
  }
  if (config.telegram?.enabled) {
    const token = env.TELEGRAM_BOT_TOKEN;
    if (!token || !/^[0-9]+:[A-Za-z0-9_-]+$/.test(token)) throw new Error("Telegram: token ausente ou inválido.");
    const base = "https://api.telegram.org/bot" + token;
    const me = await requestJson(fetcher, "Telegram", base + "/getMe");
    if (!me.ok || !me.result?.is_bot) throw new Error("Telegram: token não identifica um bot.");
    const webhook = await requestJson(fetcher, "Telegram", base + "/getWebhookInfo");
    if (!webhook.ok) throw new Error("Telegram: não foi possível verificar o webhook.");
    if (webhook.result?.url) {
      throw new Error("Telegram: este bot possui webhook em uso. Crie um bot separado para o novo projeto.");
    }
    log("Telegram: token válido e sem webhook. A conversa será liberada somente para os IDs configurados.");
  }
  if (config.linear?.enabled) {
    if (!env.LINEAR_API_KEY) throw new Error("Linear: credencial ausente.");
    log("Linear: o setup verificará a conexão e as ferramentas pelo MCP oficial.");
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const config = JSON.parse(fs.readFileSync("/opt/project-kit/integrations.json", "utf8"));
    await verifyIntegrations(config, process.env);
  } catch (error) {
    // Only our sanitized errors are emitted. Never print raw network errors or token-bearing URLs.
    console.error(error.message);
    process.exitCode = 1;
  }
}
