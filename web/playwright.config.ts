import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", fullyParallel: false, workers: 1,
  use: { baseURL: "http://127.0.0.1:5173", browserName: "chromium", headless:true, channel: process.env.PAPERX_BROWSER_CHANNEL || undefined },
  webServer: [
    { command: `"${resolve("../.venv/Scripts/python.exe")}" -m uvicorn paperx.api:app --app-dir ../backend --host 127.0.0.1 --port 8000`, url:"http://127.0.0.1:8000/health", reuseExistingServer:false },
    { command: "npm run dev", url:"http://127.0.0.1:5173", reuseExistingServer:false },
  ],
});
