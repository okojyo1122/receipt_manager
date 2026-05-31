// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const page = link.dataset.page;
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    link.classList.add('active');
    document.getElementById('page-' + page).classList.add('active');
    if (page === 'dashboard') loadDashboard();
    if (page === 'receipts') loadReceipts();
  });
});

// Upload modal
let selectedFile = null;

function openUploadModal() {
  selectedFile = null;
  document.getElementById('upload-modal').style.display = 'flex';
  document.getElementById('preview-img').style.display = 'none';
  document.getElementById('drop-zone').querySelector('.drop-zone-text').style.display = 'block';
  document.getElementById('upload-result').style.display = 'none';
  document.getElementById('upload-loading').style.display = 'none';
  document.getElementById('upload-btn').disabled = true;
  document.getElementById('file-input').value = '';
}
function closeUploadModal() {
  document.getElementById('upload-modal').style.display = 'none';
}

document.getElementById('open-upload-btn').addEventListener('click', openUploadModal);
document.getElementById('open-upload-btn2').addEventListener('click', openUploadModal);
document.getElementById('modal-close').addEventListener('click', closeUploadModal);
document.getElementById('modal-cancel').addEventListener('click', closeUploadModal);
document.getElementById('modal-overlay').addEventListener('click', closeUploadModal);

// File input
document.getElementById('file-input').addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) handleFileSelect(file);
});

// Drag & drop
const dropZone = document.getElementById('drop-zone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

function handleFileSelect(file) {
  if (!file.type.startsWith('image/')) {
    alert('画像ファイルを選択してください');
    return;
  }
  selectedFile = file;
  document.getElementById('upload-btn').disabled = false;
  const reader = new FileReader();
  reader.onload = ev => {
    const img = document.getElementById('preview-img');
    img.src = ev.target.result;
    img.style.display = 'block';
    dropZone.querySelector('.drop-zone-text').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

// Upload button
document.getElementById('upload-btn').addEventListener('click', async () => {
  if (!selectedFile) return;
  document.getElementById('upload-btn').disabled = true;
  document.getElementById('upload-loading').style.display = 'flex';
  document.getElementById('upload-result').style.display = 'none';

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const res = await fetch('/api/receipts/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'アップロードエラー');
    showUploadResult(data);
    loadDashboard();
    loadReceipts();
  } catch (err) {
    alert('エラー: ' + err.message);
    document.getElementById('upload-btn').disabled = false;
  } finally {
    document.getElementById('upload-loading').style.display = 'none';
  }
});

function showUploadResult(data) {
  document.getElementById('upload-result').style.display = 'block';
  const fmt = v => v != null ? v : '—';
  const fmtYen = v => v != null ? '¥' + v.toLocaleString() : '—';
  let html = `
    <div class="result-row"><span class="result-label">店舗名</span><span class="result-val">${fmt(data.store_name)}</span></div>
    <div class="result-row"><span class="result-label">日付</span><span class="result-val">${fmt(data.date)}</span></div>
    <div class="result-row"><span class="result-label">合計</span><span class="result-val">${fmtYen(data.total_amount)}</span></div>
  `;
  if (data.items && data.items.length > 0) {
    html += `<div class="result-items"><table>
      <thead><tr><th>商品名</th><th>数量</th><th>単価</th><th>小計</th></tr></thead>
      <tbody>`;
    for (const item of data.items) {
      html += `<tr>
        <td>${fmt(item.name)}</td>
        <td>${fmt(item.quantity)}</td>
        <td>${fmtYen(item.unit_price)}</td>
        <td>${fmtYen(item.subtotal)}</td>
      </tr>`;
    }
    html += '</tbody></table></div>';
  }
  document.getElementById('result-content').innerHTML = html;
}

// Dashboard
let monthlyChart = null;
let storeChart = null;

async function loadDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    // Stats
    const now = new Date();
    const thisMonth = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
    const monthEntry = data.monthly_spending.find(m => m.month === thisMonth);
    document.getElementById('stat-month').textContent = monthEntry ? '¥' + Math.round(monthEntry.amount).toLocaleString() : '¥0';
    document.getElementById('stat-count').textContent = data.total_receipts;
    document.getElementById('stat-total').textContent = '¥' + Math.round(data.total_spent).toLocaleString();
    document.getElementById('stat-top-store').textContent = data.spending_by_store[0]?.store || '—';

    // Monthly chart
    const months = data.monthly_spending.map(m => m.month);
    const amounts = data.monthly_spending.map(m => m.amount);
    if (monthlyChart) monthlyChart.destroy();
    monthlyChart = new Chart(document.getElementById('monthly-chart'), {
      type: 'bar',
      data: {
        labels: months,
        datasets: [{ label: '支出 (¥)', data: amounts, backgroundColor: '#4a8cff', borderRadius: 6 }]
      },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { callback: v => '¥' + v.toLocaleString() } } } }
    });

    // Store chart
    const stores = data.spending_by_store.slice(0, 8).map(s => s.store);
    const storeAmounts = data.spending_by_store.slice(0, 8).map(s => s.amount);
    const colors = ['#4a8cff','#f6ad55','#68d391','#fc8181','#b794f4','#76e4f7','#fbd38d','#a0aec0'];
    if (storeChart) storeChart.destroy();
    storeChart = new Chart(document.getElementById('store-chart'), {
      type: 'doughnut',
      data: { labels: stores, datasets: [{ data: storeAmounts, backgroundColor: colors }] },
      options: { responsive: true, plugins: { legend: { position: 'right' } } }
    });

    // Recent receipts
    const tbody = document.getElementById('recent-tbody');
    tbody.innerHTML = '';
    if (data.recent_receipts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="empty-state">データがありません</td></tr>';
    } else {
      for (const r of data.recent_receipts) {
        tbody.innerHTML += `<tr>
          <td>${r.store_name || '不明'}</td>
          <td>${r.date || '—'}</td>
          <td>¥${r.total_amount != null ? Math.round(r.total_amount).toLocaleString() : '—'}</td>
        </tr>`;
      }
    }
  } catch (err) {
    console.error('Dashboard error:', err);
  }
}

// Receipts list
async function loadReceipts() {
  try {
    const res = await fetch('/api/receipts');
    const receipts = await res.json();
    const tbody = document.getElementById('receipts-tbody');
    const empty = document.getElementById('receipts-empty');
    tbody.innerHTML = '';
    if (receipts.length === 0) {
      empty.style.display = 'block';
    } else {
      empty.style.display = 'none';
      for (const r of receipts) {
        tbody.innerHTML += `<tr>
          <td>${r.id}</td>
          <td>${r.store_name || '不明'}</td>
          <td>${r.date || '—'}</td>
          <td>¥${r.total_amount != null ? Math.round(r.total_amount).toLocaleString() : '—'}</td>
          <td><button class="btn btn-sm btn-outline" onclick="showDetail(${r.id})">詳細</button></td>
        </tr>`;
      }
    }
  } catch (err) {
    console.error('Receipts error:', err);
  }
}

// Receipt detail modal
async function showDetail(id) {
  document.getElementById('detail-modal').style.display = 'flex';
  document.getElementById('detail-body').innerHTML = '<div class="loading-wrap"><div class="spinner"></div></div>';
  try {
    const res = await fetch('/api/receipts/' + id);
    const r = await res.json();
    document.getElementById('detail-title').textContent = r.store_name || 'レシート詳細';
    const fmt = v => v != null ? v : '—';
    const fmtYen = v => v != null ? '¥' + Math.round(v).toLocaleString() : '—';
    let html = `
      <div class="result-row"><span class="result-label">店舗名</span><span class="result-val">${fmt(r.store_name)}</span></div>
      <div class="result-row"><span class="result-label">日付</span><span class="result-val">${fmt(r.date)}</span></div>
      <div class="result-row"><span class="result-label">合計金額</span><span class="result-val">${fmtYen(r.total_amount)}</span></div>
    `;
    if (r.items && r.items.length > 0) {
      html += `<div class="result-items" style="margin-top:16px"><table>
        <thead><tr><th>商品名</th><th>数量</th><th>単価</th><th>小計</th></tr></thead><tbody>`;
      for (const item of r.items) {
        html += `<tr><td>${fmt(item.name)}</td><td>${fmt(item.quantity)}</td><td>${fmtYen(item.unit_price)}</td><td>${fmtYen(item.subtotal)}</td></tr>`;
      }
      html += '</tbody></table></div>';
    }
    document.getElementById('detail-body').innerHTML = html;
  } catch (err) {
    document.getElementById('detail-body').innerHTML = '<p>エラーが発生しました</p>';
  }
}

document.getElementById('detail-close').addEventListener('click', () => {
  document.getElementById('detail-modal').style.display = 'none';
});
document.getElementById('detail-overlay').addEventListener('click', () => {
  document.getElementById('detail-modal').style.display = 'none';
});

// Price comparison
document.getElementById('price-search-btn').addEventListener('click', searchPrice);
document.getElementById('price-search').addEventListener('keydown', e => { if (e.key === 'Enter') searchPrice(); });

async function searchPrice() {
  const q = document.getElementById('price-search').value.trim();
  if (!q) return;
  document.getElementById('price-query').textContent = q;
  document.getElementById('price-results-wrap').style.display = 'block';
  const tbody = document.getElementById('price-tbody');
  tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="spinner" style="margin:auto"></div></td></tr>';
  document.getElementById('price-empty').style.display = 'none';

  try {
    const res = await fetch('/api/price-comparison?q=' + encodeURIComponent(q));
    const results = await res.json();
    tbody.innerHTML = '';
    if (results.length === 0) {
      document.getElementById('price-empty').style.display = 'block';
    } else {
      const minAvg = Math.min(...results.map(r => r.avg_price));
      for (const r of results) {
        const isBest = r.avg_price === minAvg;
        tbody.innerHTML += `<tr>
          <td>${r.store}${isBest ? ' <span class="badge badge-best">最安</span>' : ''}</td>
          <td><strong>¥${r.avg_price.toLocaleString()}</strong></td>
          <td>¥${r.min_price.toLocaleString()}</td>
          <td>¥${r.max_price.toLocaleString()}</td>
          <td>${r.count}回</td>
          <td>${r.latest_date || '—'}</td>
        </tr>`;
      }
    }
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">エラーが発生しました</td></tr>';
  }
}

// Initial load
loadDashboard();
