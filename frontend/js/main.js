// main.js — entry point, connects UI and API

let selectedFile = null;

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const btnProcess = document.getElementById('btn-process');
const btnClear = document.getElementById('btn-clear');


// --- File Selection ---

function handleFileSelect(file) {
  if (!file) return;

  const allowed = ['.txt', '.csv'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();

  if (!allowed.includes(ext)) {
    setStatus('error', 'Invalid file type. Please upload .txt or .csv');
    return;
  }

  if (file.size > 99000) {
    setStatus('error', 'File too large. Maximum size is 99KB');
    return;
  }

  selectedFile = file;
  showFileInfo(file.name);
  setButtonEnabled(true);
  hideElement('status');
  clearLog();
}

function resetAll() {
  selectedFile = null;
  fileInput.value = '';
  hideFileInfo();
  setButtonEnabled(false);
  hideElement('status');
  clearLog();
  dropzone.classList.remove('loading');
}

fileInput.addEventListener('change', (e) => {
  handleFileSelect(e.target.files[0]);
});

btnClear.addEventListener('click', () => {
  resetAll();
});


// --- Drag and Drop ---

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  handleFileSelect(e.dataTransfer.files[0]);
});

dropzone.addEventListener('click', (e) => {
  if (e.target.closest('.btn-secondary')) return;
  fileInput.click();
});


// --- Process ---

btnProcess.addEventListener('click', async () => {
  if (!selectedFile) return;

  setButtonEnabled(false);
  setStatus('loading', 'Processing your file...');
  dropzone.classList.add('loading');
  clearLog();

  try {
    addLog(`→ File received: ${selectedFile.name}`);
    addLog('→ Scanning for emails and phone numbers...');

    const blob = await maskFile(selectedFile);

    addLog('✓ Personal data removed successfully', 'success');
    addLog(`✓ File ready: masked_${selectedFile.name}`, 'success');

    setStatus('success', 'Done — your file is clean');
    downloadBlob(blob, selectedFile.name);

    setTimeout(() => {
      resetAll();
    }, 2000);

  } catch (error) {
    addLog(`✕ Error: ${error.message}`, 'error');
    setStatus('error', 'Something went wrong');
    setButtonEnabled(true);
    dropzone.classList.remove('loading');
  }
});