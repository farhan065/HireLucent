// Starts the Blogger MCP server behind an HTTP bridge.
//
// The server wants the Google client ID and secret as environment variables.
// They are read here from the mounted OAuth client file, so they are kept in
// one place and never copied into .env.
import { spawn } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'

const CLIENT_FILE = '/secrets/google_client.json'
const PORT = process.env.MCP_BLOGGER_PORT ?? '8002'

const env = { ...process.env }
if (existsSync(CLIENT_FILE)) {
  const file = JSON.parse(readFileSync(CLIENT_FILE, 'utf8'))
  const client = file.installed ?? file.web
  env.GOOGLE_CLIENT_ID = client.client_id
  env.GOOGLE_CLIENT_SECRET = client.client_secret
} else {
  console.error(`${CLIENT_FILE} not found. Publishing is unavailable until it is added.`)
}

// Messages are not logged: they contain the full text of each post.
const bridge = spawn(
  'supergateway',
  [
    '--stdio', 'node /app/dist/index.js',
    '--outputTransport', 'streamableHttp',
    '--port', PORT,
    '--healthEndpoint', '/healthz',
    '--logLevel', 'none',
  ],
  { env, stdio: 'inherit' },
)

bridge.on('exit', (code) => process.exit(code ?? 1))
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => bridge.kill(signal))
}
