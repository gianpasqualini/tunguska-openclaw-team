// OpenClaw 2026.11.3's config patch validates dynamic models before preparing
// the runtime config needed by the Codex plugin. Keep the official validator,
// but initialize its public SDK snapshot before the CLI starts.
import {
  captureRuntimeConfigAsyncReader,
  setRuntimeConfigSnapshot,
} from "/app/dist/plugin-sdk/runtime-config-snapshot.js";

setRuntimeConfigSnapshot(await captureRuntimeConfigAsyncReader()());
