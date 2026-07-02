/* === Виртуальные стенды — viewer === */
(function () {
    'use strict';

    // Cache-busting: new value every page load so updated poster images
    // always reload after a normal refresh (filenames are reused).
    const ASSET_VERSION = Date.now();

    const state = {
        catalog: null,
        currentSubject: null,
        currentPosters: [],
        filteredPosters: [],
        searchQuery: '',
        modalIndex: -1,
        modalLang: 'ru',
    };

    // === Theme ===
    function initTheme() {
        const saved = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', saved);
        document.getElementById('themeToggle').addEventListener('click', () => {
            const cur = document.documentElement.getAttribute('data-theme');
            const next = cur === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        });
    }

    // === Data loading ===
    async function loadCatalog() {
        const res = await fetch('data.json');
        if (!res.ok) throw new Error('Failed to load data.json');
        return await res.json();
    }

    // === Subject tabs ===
    function renderSubjectTabs() {
        const tabs = document.getElementById('subjectTabs');
        tabs.innerHTML = '';
        for (const subj of state.catalog.subjects) {
            const btn = document.createElement('button');
            btn.dataset.key = subj.key;
            btn.innerHTML = `${subj.title}<span class="count">${subj.count}</span>`;
            btn.addEventListener('click', () => selectSubject(subj.key));
            tabs.appendChild(btn);
        }
    }

    function selectSubject(key) {
        state.currentSubject = state.catalog.subjects.find(s => s.key === key);
        state.currentPosters = state.currentSubject.posters;
        document.querySelectorAll('#subjectTabs button').forEach(b => {
            b.classList.toggle('active', b.dataset.key === key);
        });
        localStorage.setItem('subject', key);
        applyFilter();
    }

    // === Search / filter ===
    function applyFilter() {
        const q = state.searchQuery.trim().toLowerCase();
        if (!q) {
            state.filteredPosters = state.currentPosters;
        } else {
            state.filteredPosters = state.currentPosters.filter(p => {
                if (String(p.num).padStart(3, '0').includes(q)) return true;
                if (String(p.num).includes(q)) return true;
                if (p.title_ru && p.title_ru.toLowerCase().includes(q)) return true;
                if (p.title_kz && p.title_kz.toLowerCase().includes(q)) return true;
                return false;
            });
        }
        renderGrid();
    }

    // === Grid ===
    function renderGrid() {
        const grid = document.getElementById('posterGrid');
        const empty = document.getElementById('emptyState');
        const stats = document.getElementById('stats');
        grid.innerHTML = '';

        const subj = state.currentSubject;
        const total = state.filteredPosters.length;
        if (state.searchQuery) {
            stats.textContent = `${subj.title}: найдено ${total} из ${state.currentPosters.length}`;
        } else {
            stats.textContent = `${subj.title}: ${total} стендов`;
        }

        if (total === 0) {
            empty.hidden = false;
            return;
        }
        empty.hidden = true;

        const subjKey = subj.key;
        for (let i = 0; i < state.filteredPosters.length; i++) {
            const p = state.filteredPosters[i];
            const card = document.createElement('div');
            card.className = 'card';
            card.dataset.idx = i;

            const titleHtml = p.title_ru
                ? `<div class="card-title">${escapeHtml(p.title_ru)}</div>`
                : `<div class="card-title empty">Без названия</div>`;

            card.innerHTML = `
                <div class="card-thumb">
                    <span class="card-num">№ ${p.num}</span>
                    <img loading="lazy" src="posters/${subjKey}/ru/${p.file}?v=${ASSET_VERSION}" alt="${p.num}">
                </div>
                <div class="card-body">
                    ${titleHtml}
                </div>
            `;
            card.addEventListener('click', () => openModal(i));
            grid.appendChild(card);
        }
    }

    // === Modal ===
    function openModal(idx) {
        state.modalIndex = idx;
        state.modalLang = 'ru';
        document.querySelectorAll('#langToggle button').forEach(b => {
            b.classList.toggle('active', b.dataset.lang === 'ru');
        });
        document.getElementById('modalImage').hidden = true;
        document.getElementById('placeholder').hidden = true;
        document.getElementById('modal').hidden = false;
        document.body.style.overflow = 'hidden';
        renderModal();
    }

    function closeModal() {
        document.getElementById('modal').hidden = true;
        document.body.style.overflow = '';
        state.modalIndex = -1;
    }

    function renderModal() {
        const p = state.filteredPosters[state.modalIndex];
        if (!p) return;
        if (renderModal._token === undefined) renderModal._token = 0;
        const subjKey = state.currentSubject.key;

        document.getElementById('modalNum').textContent = `№ ${p.num}`;
        const title = state.modalLang === 'ru' ? p.title_ru : p.title_kz;
        document.getElementById('modalTitle').textContent = title || '—';

        const img = document.getElementById('modalImage');
        const placeholder = document.getElementById('placeholder');
        const dl = document.getElementById('downloadBtn');

        const fileForLang = state.modalLang === 'kz' ? (p.file_kz || '') : p.file;
        const url = fileForLang ? `posters/${subjKey}/${state.modalLang}/${fileForLang}?v=${ASSET_VERSION}` : '';
        const ext = (fileForLang.split('.').pop()) || 'png';
        const fname = `${state.currentSubject.title}_${String(p.num).padStart(3, '0')}_${state.modalLang}.${ext}`;

        // Нет файла для языка (казахская версия ещё не добавлена)
        if (!url) {
            img.hidden = true;
            img.src = '';
            placeholder.hidden = false;
            dl.removeAttribute('href');
            dl.style.pointerEvents = 'none';
            dl.style.opacity = '0.4';
            document.getElementById('modalPosition').textContent =
                `${state.modalIndex + 1} из ${state.filteredPosters.length}`;
            document.getElementById('navPrev').disabled = state.modalIndex === 0;
            document.getElementById('navNext').disabled = state.modalIndex === state.filteredPosters.length - 1;
            return;
        }

        // Try to load image; if missing, show placeholder (used for KZ until added)
        const probe = new Image();
        const myToken = ++renderModal._token;
        probe.onload = () => {
            if (myToken !== renderModal._token) return;
            img.src = url;
            img.hidden = false;
            placeholder.hidden = true;
            dl.href = url;
            dl.setAttribute('download', fname);
            dl.style.pointerEvents = '';
            dl.style.opacity = '';
        };
        probe.onerror = () => {
            if (myToken !== renderModal._token) return;
            img.hidden = true;
            img.src = '';
            placeholder.hidden = false;
            dl.removeAttribute('href');
            dl.style.pointerEvents = 'none';
            dl.style.opacity = '0.4';
        };
        probe.src = url;

        document.getElementById('modalPosition').textContent =
            `${state.modalIndex + 1} из ${state.filteredPosters.length}`;

        document.getElementById('navPrev').disabled = state.modalIndex === 0;
        document.getElementById('navNext').disabled = state.modalIndex === state.filteredPosters.length - 1;
    }

    function nav(delta) {
        const next = state.modalIndex + delta;
        if (next < 0 || next >= state.filteredPosters.length) return;
        state.modalIndex = next;
        renderModal();
    }

    // === Helpers ===
    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // === Wire-up ===
    function bindEvents() {
        document.getElementById('searchInput').addEventListener('input', e => {
            state.searchQuery = e.target.value;
            applyFilter();
        });

        document.getElementById('modalClose').addEventListener('click', closeModal);
        document.getElementById('modalOverlay').addEventListener('click', closeModal);
        document.getElementById('navPrev').addEventListener('click', () => nav(-1));
        document.getElementById('navNext').addEventListener('click', () => nav(1));

        document.querySelectorAll('#langToggle button').forEach(btn => {
            btn.addEventListener('click', () => {
                state.modalLang = btn.dataset.lang;
                document.querySelectorAll('#langToggle button').forEach(b => {
                    b.classList.toggle('active', b === btn);
                });
                renderModal();
            });
        });

        document.addEventListener('keydown', e => {
            const modalOpen = !document.getElementById('modal').hidden;
            if (modalOpen) {
                if (e.key === 'Escape') closeModal();
                else if (e.key === 'ArrowLeft') nav(-1);
                else if (e.key === 'ArrowRight') nav(1);
            } else {
                if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
                    e.preventDefault();
                    document.getElementById('searchInput').focus();
                }
            }
        });
    }

    // === Лицензия: какой вариант разблокирован (0=всё, 1=биология, 2=химия, 3=физика) ===
    const VARIANT_SUBJECT = { 1: 'biology', 2: 'chemistry', 3: 'physics' };
    function getVariant(cb) {
        try {
            if (window.core && window.core.getStatus) {            // оболочка Windows (webview2/Qt)
                window.core.getStatus(function (json) {
                    try { cb(JSON.parse(json).variant_id); } catch (e) { cb(0); }
                });
                return;
            }
            if (window.AndroidShell && window.AndroidShell.getStatus) {  // Android
                try { cb(JSON.parse(window.AndroidShell.getStatus()).variant_id); } catch (e) { cb(0); }
                return;
            }
        } catch (e) {}
        cb(0);  // браузер / без оболочки → показываем всё
    }
    function gateSubjects(variant) {
        if (!variant || variant === 0) return;          // 0 = всё
        const allow = VARIANT_SUBJECT[variant];
        if (!allow) return;
        state.catalog.subjects = state.catalog.subjects.filter(s => s.key === allow);
    }

    // === Init ===
    async function init() {
        initTheme();
        try {
            state.catalog = await loadCatalog();
        } catch (e) {
            document.getElementById('posterGrid').innerHTML =
                `<div style="padding:40px;color:var(--text-muted);">Не удалось загрузить data.json. Запустите страницу через локальный сервер: <code>python -m http.server</code></div>`;
            console.error(e);
            return;
        }
        getVariant(function (variant) {
            gateSubjects(variant);
            if (!state.catalog.subjects.length) {
                document.getElementById('posterGrid').innerHTML =
                    '<div style="padding:40px;color:var(--text-muted);">Нет доступных материалов для этой лицензии.</div>';
                return;
            }
            renderSubjectTabs();
            bindEvents();
            const savedSubj = localStorage.getItem('subject');
            const initial = state.catalog.subjects.find(s => s.key === savedSubj) || state.catalog.subjects[0];
            selectSubject(initial.key);
        });
    }

    init();
})();
