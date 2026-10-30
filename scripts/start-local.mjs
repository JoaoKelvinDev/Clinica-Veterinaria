import { execFileSync } from "node:child_process";

try {
  execFileSync("docker", ["network", "inspect", "vetsys-local"], {
    stdio: "ignore",
  });
} catch {
  execFileSync(
    "docker",
    [
      "network",
      "create",
      "--driver",
      "bridge",
      "--opt",
      "com.docker.network.bridge.host_binding_ipv4=127.0.0.1",
      "vetsys-local",
    ],
    { stdio: "ignore" },
  );
}
const network = JSON.parse(
  execFileSync("docker", ["network", "inspect", "vetsys-local"], {
    encoding: "utf8",
  }),
)[0];
if (
  network.Options?.["com.docker.network.bridge.host_binding_ipv4"] !==
  "127.0.0.1"
) {
  throw new Error(
    "A rede vetsys-local precisa publicar as portas somente em 127.0.0.1.",
  );
}
console.log(
  "Iniciando PostgreSQL e Supabase Auth locais; o primeiro download pode demorar.",
);
try {
  execFileSync(
    process.execPath,
    [
      "node_modules/supabase/dist/supabase.js",
      "start",
      "--network-id",
      "vetsys-local",
      "--exclude",
      "realtime,storage-api,imgproxy,mailpit,postgres-meta,studio,edge-runtime,logflare,vector,supavisor",
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );
} catch {
  throw new Error(
    "Não foi possível iniciar o Supabase local. Verifique o Docker Desktop. Para diagnóstico, use a CLI supabase start localmente; sua saída contém chaves de desenvolvimento.",
  );
}
execFileSync(process.execPath, ["scripts/restrict-local-ports.mjs"], {
  stdio: "inherit",
});
console.log("Supabase local pronto. As credenciais não foram impressas.");
