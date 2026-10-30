import { execFileSync } from "node:child_process";
import http from "node:http";

// A CLI publica portas sem IP explícito. No Docker Desktop, a opção da rede
// não foi respeitada. Recria apenas estes dois containers com bind explícito,
// preservando volumes e configuração; não altera o daemon ou o firewall.
const context = JSON.parse(
  execFileSync("docker", ["context", "inspect"], { encoding: "utf8" }),
)[0];
const endpoint = process.env.DOCKER_HOST || context.Endpoints.docker.Host;
const socketPath = endpoint.startsWith("npipe://")
  ? endpoint.slice(8).replaceAll("/", "\\")
  : endpoint.startsWith("unix://")
    ? endpoint.slice(7)
    : null;
if (!socketPath)
  throw new Error("A restrição de portas aceita somente um Docker local.");
const version = execFileSync(
  "docker",
  ["version", "--format", "{{.Server.APIVersion}}"],
  { encoding: "utf8" },
).trim();

function request(method, path, body, archive = false) {
  const payload =
    body === undefined
      ? undefined
      : Buffer.isBuffer(body)
        ? body
        : Buffer.from(JSON.stringify(body));
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        socketPath,
        method,
        path: `/v${version}${path}`,
        headers: payload
          ? {
              "Content-Type": archive
                ? "application/x-tar"
                : "application/json",
              "Content-Length": payload.length,
            }
          : {},
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const result = Buffer.concat(chunks);
          if (response.statusCode >= 400)
            reject(
              new Error(
                `Docker local: operação ${method} recusada (${response.statusCode}).`,
              ),
            );
          else
            resolve(
              archive || !result.length
                ? result
                : JSON.parse(result.toString("utf8")),
            );
        });
      },
    );
    req.on("error", () =>
      reject(new Error("Não foi possível acessar o Docker local.")),
    );
    req.end(payload);
  });
}

for (const name of ["supabase_db_vetsys", "supabase_kong_vetsys"]) {
  const original = await request("GET", `/containers/${name}/json`);
  if (original.Config.Labels?.["com.supabase.cli.project"] !== "vetsys")
    throw new Error("Container fora do projeto local autorizado.");
  const bindings = Object.values(original.NetworkSettings.Ports ?? {}).flatMap(
    (values) => values ?? [],
  );
  if (
    bindings.length &&
    bindings.every((binding) => binding.HostIp === "127.0.0.1")
  )
    continue;
  if (
    name === "supabase_db_vetsys" &&
    !original.Mounts.some(
      (mount) =>
        mount.Type === "volume" &&
        mount.Name === "supabase_db_vetsys" &&
        mount.Destination === "/var/lib/postgresql/data",
    )
  )
    throw new Error("Volume de banco inesperado; operação cancelada.");
  const paths =
    name === "supabase_db_vetsys"
      ? [
          ["/etc/postgresql", "/etc"],
          ["/etc/postgresql-custom", "/etc"],
          ["/etc/postgresql.schema.sql", "/etc"],
        ]
      : [["/home/kong", "/home"]];
  const archives = [];
  for (const [source, destination] of paths) {
    archives.push([
      destination,
      await request(
        "GET",
        `/containers/${name}/archive?path=${encodeURIComponent(source)}`,
        undefined,
        true,
      ),
    ]);
  }
  const hostConfig = {
    ...original.HostConfig,
    PortBindings: Object.fromEntries(
      Object.entries(original.HostConfig.PortBindings).map(([port, values]) => [
        port,
        values.map((value) => ({ ...value, HostIp: "127.0.0.1" })),
      ]),
    ),
  };
  const endpoints = Object.fromEntries(
    Object.entries(original.NetworkSettings.Networks).map(
      ([network, value]) => [network, { Aliases: value.Aliases }],
    ),
  );
  const backup = `${name}_port_backup`;
  await request("POST", `/containers/${name}/stop?t=20`);
  await request("POST", `/containers/${name}/rename?name=${backup}`);
  let created;
  try {
    created = await request("POST", `/containers/create?name=${name}`, {
      ...original.Config,
      HostConfig: hostConfig,
      NetworkingConfig: { EndpointsConfig: endpoints },
    });
    for (const [destination, data] of archives)
      await request(
        "PUT",
        `/containers/${created.Id}/archive?path=${encodeURIComponent(destination)}`,
        data,
        true,
      );
    await request("POST", `/containers/${created.Id}/start`);
    let healthy = false;
    for (let attempt = 0; attempt < 45; attempt++) {
      const current = await request("GET", `/containers/${created.Id}/json`);
      if (current.State.Running && current.State.Health?.Status === "healthy") {
        healthy = true;
        break;
      }
      if (!current.State.Running) break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    if (!healthy)
      throw new Error(
        "O container local não ficou saudável após restringir a porta.",
      );
    await request("DELETE", `/containers/${original.Id}?v=false`);
  } catch (error) {
    if (created)
      await request("DELETE", `/containers/${created.Id}?force=true&v=false`);
    await request("POST", `/containers/${original.Id}/rename?name=${name}`);
    await request("POST", `/containers/${original.Id}/start`);
    throw error;
  }
}
console.log("Portas do Supabase limitadas a 127.0.0.1; volumes preservados.");
