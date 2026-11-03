import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { resolve } from "node:path";

// A saída da CLI contém chaves locais. Capture-a, sem imprimir credenciais no terminal.
const raw = execFileSync(
  process.execPath,
  ["node_modules/supabase/dist/supabase.js", "status", "-o", "json"],
  { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
);
const status = JSON.parse(raw);
if (!["127.0.0.1", "localhost"].includes(new URL(status.API_URL).hostname)) {
  throw new Error("Este script configura exclusivamente o Supabase local.");
}
const previous = existsSync(".env") ? readFileSync(".env", "utf8") : "";
const password =
  previous.match(/^LOCAL_APP_PASSWORD=(.+)$/m)?.[1] ??
  randomBytes(24).toString("hex");
const adminUrl = status.DB_URL.replace(
  "postgresql://",
  "postgresql+psycopg://",
);
const dbUrl = new URL(status.DB_URL);
dbUrl.username = "vetsys_app";
dbUrl.password = password;
const runtimeUrl = dbUrl
  .toString()
  .replace("postgresql://", "postgresql+psycopg://");
const authKey = status.PUBLISHABLE_KEY ?? status.ANON_KEY;
const secretKey = status.SECRET_KEY ?? status.SERVICE_ROLE_KEY;
writeFileSync(
  ".env",
  [
    "# Configuração LOCAL gerada; não versionar nem usar em produção.",
    `DATABASE_URL=${runtimeUrl}`,
    `MIGRATION_DATABASE_URL=${adminUrl}`,
    `SUPABASE_URL=${status.API_URL}`,
    `SUPABASE_PUBLISHABLE_KEY=${authKey}`,
    `SUPABASE_SECRET_KEY=${secretKey}`,
    `LOCAL_APP_PASSWORD=${password}`,
    `DOCKER_DATABASE_URL=${runtimeUrl.replace("127.0.0.1", "host.docker.internal")}`,
    "DOCKER_SUPABASE_URL=http://host.docker.internal:54321",
    "",
  ].join("\n"),
  { mode: 0o600 },
);
writeFileSync(
  "frontend/.env.local",
  `VITE_SUPABASE_URL=${status.API_URL}\nVITE_SUPABASE_PUBLISHABLE_KEY=${authKey}\n`,
  { mode: 0o600 },
);
execFileSync(
  "uv",
  [
    "run",
    "--env-file",
    "../.env",
    "--frozen",
    "python",
    "-m",
    "app.configure_local",
  ],
  {
    cwd: resolve("backend"),
    stdio: "inherit",
    env: { ...process.env, UV_CACHE_DIR: resolve(".cache/uv") },
  },
);
// Bucket privado dos anexos do prontuário. Idempotente: "já existe" não é erro.
const bucket = await fetch(`${status.API_URL}/storage/v1/bucket`, {
  method: "POST",
  headers: {
    apikey: secretKey,
    Authorization: `Bearer ${secretKey}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    id: "vetsys-documents",
    name: "vetsys-documents",
    public: false,
    file_size_limit: 10 * 1024 * 1024,
    allowed_mime_types: ["application/pdf", "image/jpeg", "image/png"],
  }),
});
if (!bucket.ok && ![400, 409].includes(bucket.status)) {
  throw new Error(
    `Não foi possível criar o bucket de documentos (HTTP ${bucket.status}).`,
  );
}
if (!bucket.ok && !/exist/i.test(await bucket.text())) {
  throw new Error("Não foi possível criar o bucket de documentos.");
}
console.log("Ambiente local configurado. Nenhum recurso hospedado foi criado.");
