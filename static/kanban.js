// HorizonBoard - JavaScript (monday.com style)
// Sonntag, 23. März 2026

// ===================== INLINE DROPDOWN =====================
function createDropdown(options, onSelect, cssClass) {
  const overlay = document.createElement('div');
  overlay.className = 'inline-dropdown-overlay';
  const dropdown = document.createElement('div');
  dropdown.className = 'inline-dropdown';
  options.forEach(opt => {
    const item = document.createElement('div');
    item.className = 'inline-dropdown-item';
    const badge = document.createElement('span');
    badge.className = `badge ${opt.klasse || ''}`;
    badge.textContent = opt.label;
    item.appendChild(badge);
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      onSelect(opt);
      closeDropdowns();
    });
    dropdown.appendChild(item);
  });
  overlay.appendChild(dropdown);
  overlay.addEventListener('click', closeDropdowns);
  document.body.appendChild(overlay);
  return { overlay, dropdown };
}

function positionDropdown(dropdown, triggerEl) {
  const rect = triggerEl.getBoundingClientRect();
  dropdown.style.left = rect.left + 'px';
  dropdown.style.top = (rect.bottom + 4) + 'px';
  // adjust if out of screen
  const ddRect = dropdown.getBoundingClientRect();
  if (ddRect.right > window.innerWidth - 10) {
    dropdown.style.left = (window.innerWidth - ddRect.width - 10) + 'px';
  }
}

function closeDropdowns() {
  document.querySelectorAll('.inline-dropdown-overlay').forEach(el => el.remove());
}

// ===================== INLINE STATUS EDITING =====================
document.addEventListener('click', function(e) {
  const badge = e.target.closest('[data-inline-field]');
  if (!badge) return;
  e.stopPropagation();
  closeDropdowns();

  const field = badge.dataset.inlineField;
  const entityType = badge.dataset.entityType || 'aufgabe'; // aufgabe, bug, epic
  const entityId = badge.dataset.entityId;
  const optionsRaw = JSON.parse(badge.dataset.options || '[]');

  if (!optionsRaw.length || !entityId) return;

  const { overlay, dropdown } = createDropdown(optionsRaw, async (opt) => {
    try {
      const body = {};
      body[field] = opt.value;
      const url = `/api/${entityType}/${entityId}`;
      const resp = await fetch(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await resp.json();
      if (data.success) {
        badge.textContent = opt.label;
        badge.className = `badge ${opt.klasse}`;
        // Update data-options to reflect new value if needed
        badge.dataset.currentValue = opt.value;
      } else {
        alert('Update fehlgeschlagen: ' + (data.error || 'Unbekannt'));
      }
    } catch (err) {
      console.error('Inline update error:', err);
    }
  });

  positionDropdown(dropdown, badge);
});

// ===================== GROUP ACCORDION =====================
document.addEventListener('click', function(e) {
  const header = e.target.closest('.group-header');
  if (!header) return;
  const container = header.closest('.group-container');
  if (!container) return;
  const body = container.querySelector('.group-body');
  if (!body) return;
  const toggle = header.querySelector('.group-toggle');
  body.classList.toggle('collapsed');
  if (toggle) toggle.classList.toggle('collapsed');
  // Save state
  const groupId = container.dataset.groupId;
  if (groupId) {
    const collapsed = body.classList.contains('collapsed');
    try { localStorage.setItem('group_' + groupId, collapsed ? '1' : '0'); } catch(e) {}
  }
});

// Restore accordion state
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.group-container[data-group-id]').forEach(container => {
    const groupId = container.dataset.groupId;
    try {
      const collapsed = localStorage.getItem('group_' + groupId);
      if (collapsed === '1') {
        const body = container.querySelector('.group-body');
        const toggle = container.querySelector('.group-toggle');
        if (body) body.classList.add('collapsed');
        if (toggle) toggle.classList.add('collapsed');
      }
    } catch(e) {}
  });

  // Detail tabs
  initTabs();
  // Toolbar tabs (kanban/list switch)
  initToolbarTabs();
  // Autoresize textareas
  document.querySelectorAll('textarea[data-autoresize]').forEach(ta => {
    ta.addEventListener('input', () => {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    });
  });
});

// ===================== TABS =====================
function initTabs() {
  document.querySelectorAll('.detail-tabs').forEach(tabBar => {
    const tabs = tabBar.querySelectorAll('.detail-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const panelContainer = tabBar.closest('.detail-layout')?.querySelector('.tab-panels')
          || document.querySelector('.tab-panels');
        if (panelContainer) {
          panelContainer.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.toggle('hidden', p.dataset.panel !== target);
          });
        }
      });
    });
  });
}

function initToolbarTabs() {
  document.querySelectorAll('.toolbar-tabs').forEach(tabBar => {
    const tabs = tabBar.querySelectorAll('.toolbar-tab[data-view]');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const view = tab.dataset.view;
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.querySelectorAll('[data-view-panel]').forEach(panel => {
          panel.classList.toggle('hidden', panel.dataset.viewPanel !== view);
        });
      });
    });
  });
}

// ===================== INLINE ADD ROW =====================
document.addEventListener('click', function(e) {
  const addRow = e.target.closest('.add-row');
  if (!addRow) return;
  const form = addRow.nextElementSibling;
  if (form && form.classList.contains('inline-add-form')) {
    form.classList.toggle('hidden');
    if (!form.classList.contains('hidden')) {
      const firstInput = form.querySelector('input[name="titel"]');
      if (firstInput) firstInput.focus();
    }
  }
});

// ===================== FEEDBACK VOTING =====================
document.addEventListener('click', async function(e) {
  const voteBtn = e.target.closest('.btn-vote');
  if (!voteBtn) return;
  const feedbackId = voteBtn.dataset.feedbackId;
  if (!feedbackId) return;
  try {
    const resp = await fetch(`/feedback/${feedbackId}/abstimmen`, { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      const counter = voteBtn.querySelector('.vote-count');
      if (counter) counter.textContent = data.abstimmung;
      voteBtn.classList.add('voted');
    }
  } catch (err) {
    console.error('Vote error:', err);
  }
});

// ===================== EPIC EXPAND =====================
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.epic-toggle-btn');
  if (!btn) return;
  const epicId = btn.dataset.epicId;
  document.querySelectorAll(`.epic-child-row[data-parent="${epicId}"]`).forEach(row => {
    row.classList.toggle('hidden');
  });
  btn.textContent = btn.textContent === '▶' ? '▼' : '▶';
});

// ===================== MODAL =====================
document.addEventListener('click', function(e) {
  if (e.target.matches('.modal-overlay')) {
    e.target.classList.add('hidden');
  }
  const closeBtn = e.target.closest('.modal-close');
  if (closeBtn) {
    closeBtn.closest('.modal-overlay')?.classList.add('hidden');
  }
  const openBtn = e.target.closest('[data-open-modal]');
  if (openBtn) {
    const modalId = openBtn.dataset.openModal;
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('hidden');
  }
});

// ===================== DRAG & DROP (Kanban) =====================
if (typeof Sortable !== 'undefined') {
  document.querySelectorAll('.kanban-col-body').forEach(col => {
    new Sortable(col, {
      group: 'kanban',
      animation: 150,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: async function(evt) {
        const card = evt.item;
        const aufgabeId = card.dataset.aufgabeId;
        const newStatus = evt.to.closest('.kanban-col')?.dataset.status;
        if (!aufgabeId || !newStatus) return;
        try {
          await fetch(`/api/aufgabe/${aufgabeId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
          });
          // update badge if visible
          const badge = card.querySelector('[data-inline-field="status"]');
          if (badge) badge.className = `badge status-${newStatus.toLowerCase().replace(/\s+/g, '-')}`;
        } catch (err) {
          console.error('Drag update error:', err);
        }
      }
    });
  });
}

// ===================== CONFIRM DELETES =====================
// Erstelle ein einmaliges Bestätigungs-Modal (kein window.confirm)
(function() {
  // Modal HTML einmalig in DOM einfügen
  const html = `
    <div id="delete-confirm-overlay" style="
      display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);
      z-index:9999;align-items:center;justify-content:center;">
      <div style="
        background:#fff;border-radius:10px;padding:28px 32px;max-width:420px;width:90%;
        box-shadow:0 20px 60px rgba(0,0,0,.3);font-family:inherit;">
        <div style="font-size:20px;margin-bottom:8px;">🗑️ Löschen bestätigen</div>
        <p id="delete-confirm-msg" style="color:#444;font-size:14px;margin:0 0 20px;line-height:1.5;"></p>
        <div style="display:flex;gap:10px;justify-content:flex-end;">
          <button id="delete-confirm-cancel" style="
            padding:8px 18px;border:1px solid #ddd;border-radius:6px;background:#f5f5f5;
            cursor:pointer;font-size:13px;font-weight:500;">Abbrechen</button>
          <button id="delete-confirm-ok" style="
            padding:8px 18px;border:none;border-radius:6px;background:#e53935;color:#fff;
            cursor:pointer;font-size:13px;font-weight:600;">Ja, löschen</button>
        </div>
      </div>
    </div>`;
  document.body.insertAdjacentHTML('beforeend', html);

  const overlay = document.getElementById('delete-confirm-overlay');
  const msgEl = document.getElementById('delete-confirm-msg');
  const cancelBtn = document.getElementById('delete-confirm-cancel');
  const okBtn = document.getElementById('delete-confirm-ok');
  let pendingForm = null;

  function showConfirm(msg, form) {
    msgEl.textContent = msg;
    pendingForm = form;
    overlay.style.display = 'flex';
    okBtn.focus();
  }

  function hideConfirm() {
    overlay.style.display = 'none';
    pendingForm = null;
  }

  cancelBtn.addEventListener('click', hideConfirm);
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) hideConfirm();
  });
  okBtn.addEventListener('click', function() {
    if (pendingForm) {
      pendingForm.dataset.confirmed = '1';
      pendingForm.submit();
    }
    hideConfirm();
  });

  // Fange alle Formular-Submits mit data-confirm ab
  document.addEventListener('submit', function(e) {
    const form = e.target;
    if (form.dataset.confirm && form.dataset.confirmed !== '1') {
      e.preventDefault();
      showConfirm(form.dataset.confirm, form);
    }
  }, true); // capture=true damit kein anderer Listener davor feuert
})();
