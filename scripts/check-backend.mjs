import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { parseEnv } from "node:util";

const values = parseEnv(readFileSync(".env", "utf8"));
// Passa credenciais pelo ambiente, sem colocá-las na linha de comando ou na imagem.
execFileSync(
  "docker",
  [
    "compose",
    "run",
    "--rm",
    "--no-deps",
    "-e",
    "DATABASE_URL",
    "-e",
    "MIGRATION_DATABASE_URL",
    "backend",
    "sh",
    "-c",
    "pytest && ruff check . && ruff format --check . && mypy",
  ],
  {
    env: {
      ...process.env,
      DATABASE_URL: values.DOCKER_DATABASE_URL,
      MIGRATION_DATABASE_URL: values.MIGRATION_DATABASE_URL.replace(
        "127.0.0.1",
        "host.docker.internal",
      ),
    },
    stdio: "inherit",
  },
);
