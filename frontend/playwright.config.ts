import { defineConfig, devices } from "@playwright/test";

const chromium = process.env.PW_CHROMIUM;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 45_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(chromium ? { launchOptions: { executablePath: chromium } } : {}),
      },
    },
  ],
  webServer: [
    {
      command: "bash e2e/start-stack.sh",
      url: "http://127.0.0.1:8000/health",
      stdout: "pipe",
      stderr: "pipe",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run build && npm run start -- -p 3000",
      url: "http://127.0.0.1:3000",
      env: { API_URL: "http://127.0.0.1:8000" },
      stdout: "pipe",
      stderr: "pipe",
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
    },
  ],
});
