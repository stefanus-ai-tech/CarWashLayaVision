const $ = id => document.getElementById(id);
const money = value => `Rp${Number(value || 0).toLocaleString('id-ID')}`;
const clock = seconds => {
  const n = Math.max(0, Math.floor(seconds || 0));
  return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
};
let selectedFile = null;
let libraryName = null;
let libraryItems = [];
let videoDimensions = null;
let previewUrl = null;
let currentJob = null;
let pollTimer = null;

function layoutStage(width, height) {
  if (!width || !height) return;
  videoDimensions = {width, height};
  const stage = $('videoStage');
  const availableWidth = stage.parentElement.clientWidth - 34;
  const availableHeight = window.innerHeight * 0.72;
  const ratio = width / height;
  stage.style.width = `${Math.max(180, Math.min(availableWidth, availableHeight * ratio))}px`;
  stage.style.aspectRatio = `${width} / ${height}`;
}

function updateCountMode() {
  const byLine = $('countMode').value === 'line';
  $('lineField').hidden = !byLine;
  $('directionField').hidden = !byLine;
  $('entryLine').hidden = !byLine || $('sourcePreview').hidden;
}

function chooseFile(file) {
  if (!file) return;
  const valid = ['.mp4', '.mov', '.avi', '.mkv'].some(ext => file.name.toLowerCase().endsWith(ext));
  if (!valid) { showMessage('Pilih video MP4, MOV, AVI, atau MKV.', true); return; }
  selectedFile = file;
  libraryName = null;
  $('localVideo').value = '';
  $('sourceInfo').textContent = '';
  $('fileLabel').textContent = file.name;
  $('fileHint').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB · siap dianalisis`;
  $('videoCaption').textContent = file.name;
  $('startButton').disabled = false;
  $('emptyState').hidden = true;
  $('liveFrame').hidden = true;
  $('sourcePreview').hidden = false;
  $('entryLine').hidden = false;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  $('sourcePreview').src = previewUrl;
  $('sourcePreview').currentTime = 0.1;
  $('countMode').value = 'line';
  updateCountMode();
  $('runStatus').className = 'run-status';
  $('statusText').textContent = 'Siap dianalisis';
  $('message').hidden = true;
  $('downloads').hidden = true;
}

function chooseLibrary(name) {
  const item = libraryItems.find(video => video.name === name);
  if (!item) return;
  selectedFile = null;
  libraryName = item.name;
  $('fileLabel').textContent = item.name;
  $('fileHint').textContent = `Video lokal · ${item.size_mb} MB`;
  $('sourceInfo').textContent = `${item.width} × ${item.height} · ${clock(item.duration)} · ${item.width < item.height ? 'tegak' : 'mendatar'}`;
  $('videoCaption').textContent = `${item.name} · ${item.width} × ${item.height}`;
  $('startButton').disabled = false;
  $('emptyState').hidden = true;
  $('liveFrame').hidden = true;
  $('sourcePreview').hidden = false;
  $('sourcePreview').src = `/api/library/${encodeURIComponent(item.name)}/preview`;
  $('sourcePreview').currentTime = 0.1;
  $('countMode').value = 'presence';
  layoutStage(item.width, item.height);
  updateCountMode();
  $('runStatus').className = 'run-status';
  $('statusText').textContent = 'Siap dianalisis';
  $('message').hidden = true;
  $('downloads').hidden = true;
}

async function loadLibrary() {
  try {
    const response = await fetch('/api/library');
    if (!response.ok) return;
    libraryItems = (await response.json()).videos;
    if (!libraryItems.length) return;
    $('libraryField').hidden = false;
    for (const item of libraryItems) {
      const option = document.createElement('option');
      option.value = item.name;
      option.textContent = `${item.name} · ${item.width}×${item.height}`;
      $('localVideo').append(option);
    }
  } catch (_) { /* local library is optional */ }
}

function showMessage(message, error = false) {
  const box = $('message');
  box.textContent = message;
  box.className = `message${error ? ' error' : ''}`;
  box.hidden = false;
}

function setStatus(data) {
  $('statusText').textContent = data.message;
  $('runStatus').className = `run-status ${data.status === 'error' ? 'error' : ['loading','running'].includes(data.status) ? 'active' : ''}`;
  $('countMetric').textContent = data.count;
  $('visibleMetric').textContent = data.visible;
  $('revenueMetric').textContent = money(data.revenue);
  $('timeMetric').textContent = clock(data.seconds);
  if (data.width && data.height && (!videoDimensions || videoDimensions.width !== data.width || videoDimensions.height !== data.height)) layoutStage(data.width, data.height);
  const progress = Math.round((data.progress || 0) * 100);
  $('progressBar').style.width = `${progress}%`;
  $('progressText').textContent = `${progress}%`;
  $('eventCount').textContent = `${data.event_count} RECORDS`;
  if (data.warning) showMessage(data.warning);
  if (data.status === 'error') showMessage(data.message, true);
  renderEvents(data.events);
  renderDistribution(data.by_class, data.event_count);
  if (data.status === 'done') {
    $('startButton').disabled = false;
    $('startButton').querySelector('span:first-child').textContent = 'Analisis lagi';
    renderDownloads(data.downloads);
  }
}

function renderEvents(events) {
  const body = $('eventsBody');
  body.replaceChildren();
  if (!events.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'empty-row';
    cell.textContent = 'Event akan muncul saat kendaraan melewati garis masuk.';
    row.append(cell); body.append(row);
    $('lastEmpty').hidden = false;
    $('lastContent').hidden = true;
    return;
  }
  const last = events[0];
  $('lastEmpty').hidden = true;
  $('lastContent').hidden = false;
  $('lastId').textContent = `#${last.track_id}`;
  $('lastStatus').textContent = last.status;
  $('lastBody').textContent = last.body_type || 'Belum dikenal';
  $('lastClass').textContent = last.tariff_class;
  $('lastTariff').textContent = last.tariff === '' ? 'Cek manual' : money(last.tariff);
  for (const event of events) {
    const row = document.createElement('tr');
    const values = [event.timestamp, `#${event.track_id}`, event.body_type, event.tariff_class,
      event.tariff === '' ? '—' : money(event.tariff)];
    values.forEach(value => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); });
    const cell = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `status-pill${event.status === 'Otomatis' ? '' : ' review'}`;
    badge.textContent = event.status;
    cell.append(badge); row.append(cell); body.append(row);
  }
}

function renderDistribution(counts, total) {
  const target = $('distribution');
  target.replaceChildren();
  if (!total) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = 'Belum ada data klasifikasi.'; target.append(p); return; }
  const classes = ['MOTORCYCLE','SMALL','MEDIUM','LARGE','COMMERCIAL','REVIEW'];
  for (const name of classes) {
    const count = counts[name] || 0;
    if (!count) continue;
    const row = document.createElement('div'); row.className = 'dist-row';
    const label = document.createElement('span'); label.textContent = name;
    const bar = document.createElement('div'); bar.className = 'dist-bar';
    const fill = document.createElement('i'); fill.style.width = `${count / total * 100}%`; bar.append(fill);
    const number = document.createElement('b'); number.textContent = count;
    row.append(label, bar, number); target.append(row);
  }
}

function renderDownloads(files) {
  const target = $('downloads'); target.replaceChildren();
  for (const filename of files) {
    const link = document.createElement('a');
    link.href = `/api/jobs/${currentJob}/download/${encodeURIComponent(filename)}`;
    link.textContent = `↓ Unduh ${filename}`;
    target.append(link);
  }
  target.hidden = files.length === 0;
}

async function poll() {
  if (!currentJob) return;
  try {
    const response = await fetch(`/api/jobs/${currentJob}`, {cache:'no-store'});
    if (!response.ok) throw new Error('Status analisis tidak terbaca.');
    const data = await response.json();
    setStatus(data);
    if (data.status === 'done' || data.status === 'error') {
      clearInterval(pollTimer); pollTimer = null;
      if (data.status === 'error') $('startButton').disabled = false;
    }
    return data.status;
  } catch (error) { showMessage(error.message, true); return 'error'; }
}

async function start(event) {
  event.preventDefault();
  if ((!selectedFile && !libraryName) || pollTimer) return;
  $('startButton').disabled = true;
  $('downloads').hidden = true;
  $('message').hidden = true;
  $('statusText').textContent = 'Mengunggah video...';
  $('runStatus').className = 'run-status active';
  const form = new FormData($('settingsForm'));
  if (libraryName) form.set('library_name', libraryName);
  else form.set('video', selectedFile);
  form.set('line', String(Number($('line').value) / 100));
  form.set('threshold', String(Number($('threshold').value) / 100));
  form.set('use_laya', String($('useLaya').checked));
  try {
    const response = await fetch('/api/jobs', {method:'POST', body:form});
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Upload gagal.');
    currentJob = result.id;
    $('sourcePreview').hidden = true;
    $('entryLine').hidden = true;
    $('liveFrame').hidden = false;
    $('liveFrame').src = `/api/jobs/${currentJob}/stream`;
    const status = await poll();
    if (!['done', 'error'].includes(status)) pollTimer = setInterval(poll, 700);
  } catch (error) {
    showMessage(error.message, true);
    $('statusText').textContent = 'Gagal memulai';
    $('runStatus').className = 'run-status error';
    $('startButton').disabled = false;
  }
}

$('videoFile').addEventListener('change', event => chooseFile(event.target.files[0]));
$('localVideo').addEventListener('change', event => chooseLibrary(event.target.value));
$('sourcePreview').addEventListener('loadedmetadata', event => layoutStage(event.target.videoWidth, event.target.videoHeight));
window.addEventListener('resize', () => { if (videoDimensions) layoutStage(videoDimensions.width, videoDimensions.height); });
$('countMode').addEventListener('change', updateCountMode);
const dropzone = $('dropzone');
['dragenter','dragover'].forEach(name => dropzone.addEventListener(name, event => {event.preventDefault(); dropzone.classList.add('dragging');}));
['dragleave','drop'].forEach(name => dropzone.addEventListener(name, event => {event.preventDefault(); dropzone.classList.remove('dragging');}));
dropzone.addEventListener('drop', event => chooseFile(event.dataTransfer.files[0]));
$('line').addEventListener('input', event => { $('lineValue').textContent = `${event.target.value}%`; $('entryLine').style.top = `${event.target.value}%`; });
$('threshold').addEventListener('input', event => { $('thresholdValue').textContent = `${event.target.value}%`; });
$('entryLine').style.top = `${$('line').value}%`;
$('settingsForm').addEventListener('submit', start);
loadLibrary();
