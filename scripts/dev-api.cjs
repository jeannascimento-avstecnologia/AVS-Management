const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const venvPython =
  process.platform === 'win32'
    ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : path.join(root, '.venv', 'bin', 'python')

if (!fs.existsSync(venvPython)) {
  const activateHint =
    process.platform === 'win32'
      ? '  .venv\\Scripts\\activate'
      : '  source .venv/bin/activate'
  console.error(
    '[dev:api] Virtualenv não encontrado (ou criado em outro SO). Na raiz do projeto:\n' +
      '  python3.12 -m venv .venv\n' +
      activateHint +
      '\n' +
      '  pip install -r requirements.txt',
  )
  process.exit(1)
}

console.log('[dev:api] UI = http://127.0.0.1:5173  |  API = http://127.0.0.1:8000 (HTML redireciona)')

const child = spawn(
  venvPython,
  [
    '-m',
    'uvicorn',
    'src.main:app',
    '--reload',
    '--reload-dir',
    'src',
    '--host',
    '127.0.0.1',
    '--port',
    '8000',
  ],
  {
    cwd: root,
    stdio: 'inherit',
    shell: false,
    env: { ...process.env, AVS_SPA_DEV: '1' },
  },
)

child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal)
  process.exit(code ?? 0)
})
