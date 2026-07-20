const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const venvPython =
  process.platform === 'win32'
    ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : path.join(root, '.venv', 'bin', 'python')

if (!fs.existsSync(venvPython)) {
  console.error(
    '[dev:api] Virtualenv não encontrado. Na raiz do projeto:\n' +
      '  python -m venv .venv\n' +
      '  .venv\\Scripts\\activate   (Windows)\n' +
      '  pip install -r requirements.txt',
  )
  process.exit(1)
}

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
  { cwd: root, stdio: 'inherit', shell: false },
)

child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal)
  process.exit(code ?? 0)
})
