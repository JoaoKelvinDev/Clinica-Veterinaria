import { execFileSync } from "node:child_process";
import { connect } from "node:net";

// O Docker só informa "ports are not available"; antes de subir, explique o que liberar.
// No Windows, abrir um servidor de teste pode ter sucesso mesmo com a porta em uso,
// por isso a verificação tenta conectar.
function portFree(port) {
  return new Promise((resolve) => {
    const socket = connect({ port, host: "127.0.0.1" })
      .once("connect", () => {
        socket.destroy();
        resolve(false);
      })
      .once("error", () => resolve(true));
    socket.setTimeout(1000, () => {
      socket.destroy();
      resolve(true);
    });
  });
}

function composeOwns(service) {
  try {
    return (
      execFileSync(
        "docker",
        ["compose", "ps", "--status", "running", "--quiet", service],
        {
          encoding: "utf8",
          stdio: ["ignore", "pipe", "ignore"],
        },
      ).trim() !== ""
    );
  } catch {
    return false;
  }
}

const ports = [
  [5173, "frontend", "o frontend (Vite)"],
  [8000, "backend", "a API"],
];
const busy = [];
for (const [port, service, label] of ports) {
  if (!(await portFree(port)) && !composeOwns(service))
    busy.push(`${port} (${label})`);
}
if (busy.length) {
  console.error(
    [
      `Porta ocupada por outro programa: ${busy.join(", ")}.`,
      "Provavelmente um `npm run dev` iniciado dentro de frontend/ ou um uvicorn em outro terminal.",
      "Feche esse terminal (Ctrl+C) e rode `npm run dev` de novo na raiz.",
      "No PowerShell, para ver quem usa a porta:",
      "  Get-NetTCPConnection -LocalPort 5173 -State Listen | Select-Object OwningProcess",
    ].join("\n"),
  );
  process.exit(1);
}

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
