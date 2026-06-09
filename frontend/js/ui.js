// ui.js — all DOM manipulation and UI state

function showElement(id) {
  document.getElementById(id).classList.remove('hidden');
}

function hideElement(id) {
  document.getElementById(id).classList.add('hidden');
}

function setStatus(state, text) {
  const indicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');

  showElement('status');
  indicator.className = `status-indicator ${state}`;
  statusText.textContent = text;
}

function addLog(message, type = 'default') {
  const logList = document.getElementById('log-list');
  showElement('log-panel');

  const item = document.createElement('li');
  item.className = `log-item ${type}`;
  item.textContent = message;
  logList.appendChild(item);
}

function clearLog() {
  document.getElementById('log-list').innerHTML = '';
  hideElement('log-panel');
}

function showFileInfo(filename) {
  document.getElementById('file-name').textContent = filename;
  showElement('file-info');
}

function hideFileInfo() {
  hideElement('file-info');
}

function setButtonEnabled(enabled) {
  document.getElementById('btn-process').disabled = !enabled;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `masked_${filename}`;
  a.click();
  URL.revokeObjectURL(url);
}