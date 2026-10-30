import { execFileSync } from "node:child_process";

execFileSync(process.execPath, ["scripts/start-local.mjs"], {
  stdio: "inherit",
});
execFileSync(process.execPath, ["scripts/setup-local.mjs"], {
  stdio: "inherit",
});
execFileSync("docker", ["compose", "up", "--build", "--detach", "--wait"], {
  stdio: "inherit",
});
console.log("Aplicação disponível em http://localhost:5173");
