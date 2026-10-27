/* Мини-приложение клуба Единение: все данные с сервера, вход через Telegram */
const TG = window.Telegram && window.Telegram.WebApp;
const DEV = new URLSearchParams(location.search).get("dev") || "";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const MONTHS = ["янв","февр","марта","апр","мая","июня","июля","авг","сент","окт","нояб","дек"];
const WD = ["Вс","Пн","Вт","Ср","Чт","Пт","Сб"];

let S = {me:null, points:null, rules:[], shop:[], events:{soon:[],records:[]}, feed:[], filter:"all", newMatches:0};

/* ---------- сервер ---------- */
async function api(path, opts = {}) {
  const headers = {"X-Init-Data": TG ? TG.initData : "", ...(DEV ? {"X-Dev-User": DEV} : {})};
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const r = await fetch(path, {method: opts.method || (opts.body ? "POST" : "GET"), headers, body: opts.body});
  let data = null; try { data = await r.json(); } catch (e) {}
  if (!r.ok) { const err = new Error((data && data.detail) || "Ошибка сервера"); err.status = r.status; throw err; }
  return data;
}
let tt; function toast(t) { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(tt); tt = setTimeout(() => el.classList.remove("on"), 2600); }
function fail(e) { toast(e.message && !e.message.startsWith("{") ? e.message : "Не получилось, попробуйте еще раз"); }
function copy(t) { try { navigator.clipboard.writeText(t).catch(() => {}); } catch (e) {} }
function openTg(username) {
  const url = "https://t.me/" + username.replace("@", "");
  if (TG && TG.openTelegramLink) TG.openTelegramLink(url); else window.open(url, "_blank");
}
function haptic(type) { try { TG.HapticFeedback.impactOccurred(type || "light"); } catch (e) {} }

/* ---------- внешний вид ---------- */
(function logo() { let h = ""; for (let i = 0; i < 48; i++) { const a = i / 48 * Math.PI * 2, r1 = i % 2 ? 7 : 5, r2 = i % 2 ? 15 : 19;
  h += `<line x1="${20 + r1 * Math.cos(a)}" y1="${20 + r1 * Math.sin(a)}" x2="${20 + r2 * Math.cos(a)}" y2="${20 + r2 * Math.sin(a)}" stroke="currentColor" stroke-width=".7" stroke-linecap="round"/>`; }
  $("#logo").innerHTML = h; })();
const ORBS = [["#F2B394","#B0583F","#2A1218"],["#DCE6FF","#7189CF","#1A2140"],["#E8C9A0","#A0704A","#24170F"],["#E9B6C6","#9A4C6A","#24111C"],["#BFE0D0","#4E8C78","#0F1F1C"]];
const orb = id => { const o = ORBS[Math.abs(Number(id) || 0) % ORBS.length];
  return `radial-gradient(70% 60% at 82% 0%,${o[0]} 0%,${o[1]} 28%,transparent 62%),radial-gradient(90% 70% at 10% 110%,${o[2]} 0%,transparent 70%),#0F1224`; };
const avaBg = id => { const o = ORBS[Math.abs(Number(id) || 0) % ORBS.length]; return `radial-gradient(circle at 50% 20%,${o[1]},${o[2]} 70%)`; };
const initials = p => ((p.first_name || "?")[0] + ((p.last_name || "")[0] || "")).toUpperCase();
const fullName = p => [p.first_name, p.last_name ? p.last_name[0] + "." : ""].filter(Boolean).join(" ") || "Участник клуба";
const lockSVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/></svg>';
const ICONS = {
 rec:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="6" width="13" height="12" rx="3"/><path d="M16 10.5l5-3v9l-5-3"/></svg>',
 note:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M7 4h7l4 4v12H7z"/><path d="M10 12h5M10 15.5h5"/></svg>',
 pod:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0013 0M12 18v2.5"/></svg>',
 guide:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 4h12v16H6z"/><path d="M9 9l1.5 1.5L13.5 7.5M9 15h6"/></svg>',
 case:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 18l5-6 4 3 7-8"/><path d="M15 7h5v5"/></svg>',
 clip:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><rect x="6" y="3" width="12" height="18" rx="3"/><path d="M10.5 9.5l4 2.5-4 2.5z"/></svg>',
 gift:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="9" width="16" height="11" rx="2"/><path d="M3 9h18M12 9v11M12 9c-1.5-3-5-4-5-1.5S12 9 12 9zm0 0c1.5-3 5-4 5-1.5S12 9 12 9z"/></svg>',
 house:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 11l9-7 9 7M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/></svg>',
 talk:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M4 5h16v11H9l-5 4z"/></svg>'
};
const TYPE = {rec:"Запись эфира", note:"Конспект", pod:"Подкаст", guide:"Гайд спикера", case:"Кейс участника", clip:"Нарезка"};
function when(iso) { const d = new Date(iso); return {d: String(d.getDate()).padStart(2, "0"), m: MONTHS[d.getMonth()], wd: WD[d.getDay()],
  t: d.toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow"})}; }

/* ---------- окна ---------- */
function openSheet(html, bind) { $("#sheet").innerHTML = '<div class="grab"></div>' + html; $("#sheetWrap").hidden = false; bind && bind($("#sheet")); }
function closeSheet() { $("#sheetWrap").hidden = true; }
$("#sheetWrap").onclick = e => { if (e.target.id === "sheetWrap") closeSheet(); };
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeSheet(); $("#matchOv").hidden = true; } });

/* ---------- навигация ---------- */
const TITLES = {home:["Клуб","Главная"], events:["Встречи клуба","Эфиры"], lib:["Знания клуба","Библиотека"], people:["Круг","Люди"], profile:["Ваше участие","Профиль"]};
function go(v, seg) {
  $$("nav.tabs button").forEach(x => x.setAttribute("aria-selected", x.dataset.v === v ? "true" : "false"));
  $$(".view").forEach(x => x.classList.toggle("on", x.id === "v-" + v));
  $("#eyebrow").textContent = TITLES[v][0]; $("#title").textContent = TITLES[v][1];
  if (v === "people") { if (seg) peopleSeg(seg); }
  if (v === "lib") loadLib();
  window.scrollTo(0, 0);
}
$$("nav.tabs button").forEach(b => b.onclick = () => go(b.dataset.v));
$("#ptsPill").onclick = () => go("profile");
document.addEventListener("click", e => { const t = e.target.closest("[data-tab]"); if (t) go(t.dataset.tab, t.dataset.seg); });
function route() { const h = location.hash.slice(1);
  if (h === "coffee" || h === "matches") go("people", h); else if (TITLES[h]) go(h); }

/* ---------- баллы ---------- */
function setPoints(p) {
  S.points = p; $$(".ptsv").forEach(e => e.textContent = p.balance);
  const next = S.shop.filter(x => !x.inside_only).map(x => x.cost).filter(c => c > p.balance).sort((a, b) => a - b)[0];
  const item = S.shop.find(x => x.cost === next);
  $("#goalOf").textContent = next ? ` / ${next}` : "";
  $("#prog").style.width = next ? Math.min(100, p.balance / next * 100) + "%" : "100%";
  $("#goalText").textContent = (next ? `До награды «${item.title}» осталось ${next - p.balance}. ` : "Хватает на любую награду из раздела «Профиль». ")
    + (p.pending ? `На проверке еще ${p.pending}.` : "Баллы даются за вклад в клуб, а не за присутствие.");
}
async function refreshPoints() { const d = await api("/api/points"); S.rules = d.rules; S.shop = d.shop; S.invite = d.invite_link; S.claims = d.claims;
  setPoints({balance: d.balance, pending: d.pending}); renderTasks(); renderShop(); }

function renderTasks() {
  const pendingCodes = new Set((S.claims || []).filter(c => c.status === "pending").map(c => c.rule_code));
  const rules = S.rules.filter(r => r.code !== "coffee");
  $("#tasks").innerHTML = rules.map(k => `<div class="task${pendingCodes.has(k.code) ? " done" : ""}"><div class="t"><b>${esc(k.title)} <span class="plus">+${k.points}</span></b><span>${esc(k.hint)}</span></div>
    <button class="btn sm" data-task="${esc(k.code)}">${pendingCodes.has(k.code) ? "Еще раз" : "Сделать"}</button></div>`).join("");
  $$("[data-task]").forEach(b => b.onclick = () => taskSheet(S.rules.find(k => k.code === b.dataset.task)));
}
function taskSheet(k, ref) {
  if (k.kind === "link") {
    openSheet(`<h3>${esc(k.title)}</h3><p class="sub">Ваша личная ссылка. Когда друг оплатит участие, баллы придут на подтверждение сами.</p>
      <div class="msg">${esc(S.invite)}</div><button class="btn" id="cp">Скопировать ссылку</button>`,
      s => s.querySelector("#cp").onclick = () => { copy(S.invite); toast("Ссылка скопирована"); closeSheet(); });
    return;
  }
  openSheet(`<h3>${esc(k.title)}</h3><p class="sub">${esc(k.hint)}. После проверки командой клуба на балансе появится +${k.points}.</p>
    ${k.kind === "file" ? '<label class="f" for="tf">СКРИНШОТ<input type="file" id="tf" accept="image/*"></label>' : ""}
    <label class="f" for="tx">${k.kind === "file" ? "КОММЕНТАРИЙ" : "ВАШ ТЕКСТ"}<textarea id="tx" rows="4"></textarea></label>
    <button class="btn" id="snd">Отправить на подтверждение</button>`, s => s.querySelector("#snd").onclick = async () => {
      const fd = new FormData(); fd.append("rule_code", k.code); fd.append("text", s.querySelector("#tx").value); if (ref) fd.append("ref", ref);
      const f = s.querySelector("#tf"); if (f && f.files[0]) fd.append("file", f.files[0]);
      if (k.kind === "file" && !(f && f.files[0])) { toast("Приложите скриншот"); return; }
      try { s.querySelector("#snd").disabled = true; await api("/api/claims", {body: fd}); closeSheet(); toast(`+${k.points} ждут подтверждения`); haptic("medium"); refreshPoints(); }
      catch (e) { s.querySelector("#snd").disabled = false; fail(e); }
    });
}
function renderShop() {
  const inside = S.me.level === "inside";
  $("#shop").innerHTML = S.shop.map(s => `<div class="item" style="cursor:default"><div class="ic">${ICONS[s.icon] || ICONS.gift}</div>
    <div class="t"><b>${esc(s.title)}</b><span>${esc(s.hint)}</span></div>
    <div class="end" style="flex-direction:column;align-items:flex-end;gap:6px"><span class="plus">${s.cost}</span>
    ${s.inside_only && !inside ? `<span class="lock">${lockSVG}Inside</span>` : `<button class="btn sm" data-buy="${esc(s.code)}" ${S.points.balance < s.cost ? "disabled" : ""}>${S.points.balance < s.cost ? "Копим" : "Обменять"}</button>`}</div></div>`).join("");
  $$("[data-buy]").forEach(b => b.onclick = async () => { try { await api("/api/shop/" + b.dataset.buy, {method: "POST"}); toast("Заявка отправлена, менеджер напишет вам"); refreshPoints(); } catch (e) { fail(e); } });
}

/* ---------- эфиры ---------- */
async function loadEvents() { S.events = await api("/api/events"); renderEvents(); renderHero(); }
function evRow(e) { const w = when(e.starts_at);
  return `<button class="item" data-ev="${e.id}"><div class="date"><b>${w.d}</b><span>${w.m}</span></div>
    <div class="t"><b>${esc(e.title)}</b><span>${w.wd}, ${w.t} · ${esc(e.rubric || "Эфир")} · ${esc(e.place)}</span></div>
    <div class="end">${e.locked ? `<span class="lock">${lockSVG}Inside</span>` : e.going ? '<span class="going">Иду</span>' : ""}</div></button>`; }
function renderEvents() {
  const {soon, records} = S.events;
  $("#evSoon").innerHTML = soon.length ? soon.map(evRow).join("") + '<p class="sub">Бот напомнит за день и за час до начала.</p>' : '<p class="empty-line">Ближайшие эфиры появятся здесь, как только команда их назначит.</p>';
  $("#evRec").innerHTML = records.length ? records.map(r => `<button class="item" data-rec="${r.id}"><div class="ic">${ICONS.rec}</div>
    <div class="t"><b>${esc(r.title)}</b><span>${esc(r.speaker)} · ${when(r.starts_at).d} ${when(r.starts_at).m}</span></div><div class="end">${r.locked ? `<span class="lock">${lockSVG}Inside</span>` : "запись"}</div></button>`).join("")
    : '<p class="empty-line">Записи прошедших эфиров с конспектами будут собираться здесь.</p>';
  $$("[data-ev]").forEach(b => b.onclick = () => eventSheet(soon.find(e => e.id == b.dataset.ev)));
  $$("[data-rec]").forEach(b => b.onclick = () => recSheet(records.find(e => e.id == b.dataset.rec)));
}
function renderHero() {
  const e = S.events.soon[0];
  if (!e) { $("#heroBox").innerHTML = `<div class="hero"><span class="k">Клуб Единение</span><h3>Добро пожаловать${S.me.first_name ? ", " + esc(S.me.first_name) : ""}</h3><p>Здесь появится ближайший эфир. Пока загляните в «Люди»: там уже ждут знакомства.</p><div class="btns"><button class="btn sm" data-tab="people">Найти своих</button></div></div>`; return; }
  const w = when(e.starts_at);
  $("#heroBox").innerHTML = `<div class="hero"><span class="k">Ближайший эфир · ${w.wd} ${w.d} ${w.m}, ${w.t} МСК</span><h3>${esc(e.title)}</h3>
    <p>${esc([e.rubric, e.speaker, e.place].filter(Boolean).join(" · "))}</p>
    <div class="btns"><button class="btn sm" id="heroGo">${e.locked ? "Только Inside" : e.going ? "Вы идете" : "Буду"}</button><button class="btn sm ghost" data-tab="events">Все эфиры</button></div></div>`;
  $("#heroGo").onclick = () => eventSheet(e);
}
function eventSheet(e) { const w = when(e.starts_at);
  openSheet(`<p class="sub">${w.wd}, ${w.d} ${w.m} · ${w.t} МСК · ${esc(e.place)}</p><h3>${esc(e.title)}</h3>
    <div class="tags">${e.rubric ? `<span class="tag">${esc(e.rubric)}</span>` : ""}${e.speaker ? `<span class="tag">${esc(e.speaker)}</span>` : ""}${e.inside_only ? `<span class="lock">${lockSVG}Inside-level</span>` : ""}</div>
    ${e.description ? `<p style="margin:0">${esc(e.description)}</p>` : ""}
    ${e.locked ? '<p class="sub">Закрытое событие для участников Inside-level. Условия перехода в разделе «Профиль».</p>'
      : `<p class="sub">${e.going ? "Вы записаны. Бот напомнит за день и за час." : "Отметьтесь, и бот пришлет ссылку и напомнит о начале. После эфира оставьте инсайт: он засчитает участие и даст баллы."}</p>
        ${e.going && e.join_url ? `<a class="btn" href="${esc(e.join_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Подключиться</a>` : ""}
        <button class="btn ${e.going ? "ghost" : ""}" id="eg">${e.going ? "Не смогу прийти" : "Буду"}</button>`}`,
    s => { const b = s.querySelector("#eg"); if (b) b.onclick = async () => {
      try { const r = await api(`/api/events/${e.id}/rsvp`, {method: "POST"}); e.going = r.going; e.join_url = r.join_url; toast(r.going ? "Отлично, бот напомнит" : "Отметка снята"); renderEvents(); renderHero(); closeSheet(); haptic(); }
      catch (err) { fail(err); } }; });
}
function recSheet(r) { const w = when(r.starts_at);
  const ideas = r.summary || [], ts = r.timecodes || [];
  openSheet(`<p class="sub">${esc(r.speaker)} · ${w.d} ${w.m}</p><h3>${esc(r.title)}</h3>
    ${r.locked ? '<p class="sub">Запись доступна участникам Inside-level.</p>' : `
    <div class="btns">${r.recording_url ? `<a class="btn sm" href="${esc(r.recording_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Смотреть запись</a>` : ""}
      ${r.podcast_url ? `<a class="btn sm ghost" href="${esc(r.podcast_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Слушать подкастом</a>` : ""}</div>
    ${ideas.length ? `<div><p class="sub" style="margin-bottom:6px">Главное из эфира</p><ul>${ideas.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>` : ""}
    ${ts.length ? `<div><p class="sub" style="margin-bottom:6px">Таймкоды</p><div class="ts">${ts.map(t => `<div><b>${esc(t[0])}</b><span>${esc(t[1])}</span></div>`).join("")}</div></div>` : ""}
    <button class="btn" id="ins">Оставить инсайт</button>`}`,
    s => { const b = s.querySelector("#ins"); if (b) b.onclick = () => taskSheet(S.rules.find(k => k.code === "insight"), "event:" + r.id); });
}
$$("[data-es]").forEach(b => b.onclick = () => { $$("[data-es]").forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
  $("#evSoon").hidden = b.dataset.es !== "soon"; $("#evRec").hidden = b.dataset.es !== "rec"; });

/* ---------- библиотека ---------- */
let libType = "all", libTimer;
$("#libChips").innerHTML = [["all","Все"],["rec","Записи"],["note","Конспекты"],["pod","Подкасты"],["clip","Нарезки"],["guide","Гайды"],["case","Кейсы"]]
  .map(([k, v]) => `<button class="chip" data-lt="${k}" aria-pressed="${k === "all"}">${v}</button>`).join("");
$$("[data-lt]").forEach(c => c.onclick = () => { $$("[data-lt]").forEach(x => x.setAttribute("aria-pressed", x === c ? "true" : "false")); libType = c.dataset.lt; loadLib(); });
$("#libSearch").oninput = () => { clearTimeout(libTimer); libTimer = setTimeout(loadLib, 300); };
const libItem = x => `<button class="item" data-lib="${x.id}"><div class="ic">${ICONS[x.type] || ICONS.note}</div>
  <div class="t"><b>${esc(x.title)}</b><span>${esc([TYPE[x.type], x.author, x.meta].filter(Boolean).join(" · "))}</span></div>
  <div class="end">${x.locked ? `<span class="lock">${lockSVG}Inside</span>` : ""}</div></button>`;
function bindLib(root, items) { root.querySelectorAll("[data-lib]").forEach(b => b.onclick = () => libSheet(items.find(x => x.id == b.dataset.lib))); }
async function loadLib() {
  try { const items = await api(`/api/library?type=${libType}&q=${encodeURIComponent($("#libSearch").value)}`);
    $("#libList").innerHTML = items.length ? items.map(libItem).join("") : '<p class="empty-line">Здесь пока пусто. Материалы появятся после первых эфиров.</p>';
    bindLib($("#libList"), items); } catch (e) { fail(e); }
}
async function loadHomeLib() { const items = (await api("/api/library")).slice(0, 3);
  $("#homeLib").innerHTML = items.length ? items.map(libItem).join("") : '<p class="empty-line">Первые материалы появятся после эфиров клуба.</p>'; bindLib($("#homeLib"), items); }
function libSheet(x) {
  openSheet(`<p class="sub">${esc([TYPE[x.type], x.author, x.meta].filter(Boolean).join(" · "))}</p><h3>${esc(x.title)}</h3>
    ${x.locked ? '<p class="sub">Материал открыт участникам Inside-level.</p>'
      : `${x.body ? `<div style="white-space:pre-wrap;font-size:15px">${esc(x.body)}</div>` : ""}
         ${x.url ? `<a class="btn" href="${esc(x.url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Открыть</a>` : ""}`}`);
}

/* ---------- люди ---------- */
function peopleSeg(k) { $$("[data-ps]").forEach(x => x.setAttribute("aria-pressed", x.dataset.ps === k ? "true" : "false"));
  ["feed", "coffee", "matches"].forEach(n => $("#p-" + n).hidden = n !== k);
  if (k === "matches") { S.newMatches = 0; updBadge(); loadMatches(); }
  if (k === "coffee") loadCoffee(); }
$$("[data-ps]").forEach(b => b.onclick = () => peopleSeg(b.dataset.ps));
$$("[data-f]").forEach(c => c.onclick = () => { $$("[data-f]").forEach(x => x.setAttribute("aria-pressed", x === c ? "true" : "false")); S.filter = c.dataset.f; loadFeed(); });
async function loadFeed() { try { S.feed = await api("/api/feed?f=" + S.filter); renderDeck(); } catch (e) { fail(e); } }
const cardHTML = (p, top) => `<article class="card${top ? "" : " back"}" data-id="${p.tg_id}">
  <div class="cover" style="background:${orb(p.tg_id)}"><div class="ini">${esc(initials(p))}</div><div class="who"><b>${esc(fullName(p))}</b><span>${esc([p.sphere, p.city].filter(Boolean).join(" · "))}</span></div>
  ${top ? '<span class="stamp yes">Знакомимся</span><span class="stamp no">Дальше</span>' : ""}</div>
  <div class="body">${p.project ? `<div class="r"><span class="lbl">Проект</span><p>${esc(p.project)}</p></div>` : ""}
   <div class="r"><span class="lbl">Ищет</span><p>${esc(p.seek)}</p></div><div class="r"><span class="lbl">Может помочь</span><p>${esc(p.give)}</p></div>
   <div class="tags">${p.level === "inside" ? '<span class="tag">inside</span>' : ""}${p.offline ? '<span class="tag">офлайн</span>' : ""}</div></div></article>`;
function renderDeck() {
  const d = $("#deck");
  if (!S.feed.length) { d.innerHTML = `<div class="empty"><h3>Вы посмотрели всех</h3><p>Новые участники появятся после вступления в клуб, бот пришлет уведомление.</p></div>`; return; }
  d.innerHTML = S.feed.slice(0, 2).reverse().map((p, i, a) => cardHTML(p, i === a.length - 1)).join("");
  bindDrag(d.querySelector(".card:not(.back)"));
}
function bindDrag(el) {
  let x0 = 0, y0 = 0, dx = 0, dy = 0, down = false; const yes = el.querySelector(".stamp.yes"), no = el.querySelector(".stamp.no");
  el.onpointerdown = e => { down = true; x0 = e.clientX; y0 = e.clientY; el.setPointerCapture(e.pointerId); el.classList.add("dragging"); };
  el.onpointermove = e => { if (!down) return; dx = e.clientX - x0; dy = e.clientY - y0; el.style.transform = `translate(${dx}px,${dy * .3}px) rotate(${dx / 18}deg)`;
    yes.style.opacity = Math.max(0, Math.min(1, dx / 90)); no.style.opacity = Math.max(0, Math.min(1, -dx / 90)); };
  el.onpointerup = el.onpointercancel = () => { if (!down) return; down = false; el.classList.remove("dragging");
    if (dx > 100) decide(true); else if (dx < -100) decide(false); else { el.style.transform = ""; yes.style.opacity = 0; no.style.opacity = 0; } dx = 0; };
}
async function decide(like) {
  const el = $("#deck .card:not(.back)"); if (!el) return; const p = S.feed.shift();
  el.style.transform = `translate(${like ? 520 : -520}px,40px) rotate(${like ? 24 : -24}deg)`; el.style.opacity = 0; haptic();
  setTimeout(renderDeck, 260);
  try { const r = await api("/api/like", {json: {to_id: p.tg_id, like}});
    if (r.match) showMatch(r.match); else if (like) toast(`${p.first_name || "Участник"} увидит вашу отметку`);
    if (S.feed.length < 3) { const more = await api("/api/feed?f=" + S.filter); const have = new Set(S.feed.map(x => x.tg_id)); S.feed.push(...more.filter(x => !have.has(x.tg_id) && x.tg_id !== p.tg_id)); }
  } catch (e) { fail(e); }
}
function showMatch(p) {
  S.newMatches++; updBadge(); try { TG.HapticFeedback.notificationOccurred("success"); } catch (e) {}
  $("#ovMe").textContent = initials(S.me); $("#ovMe").style.background = avaBg(S.me.tg_id);
  $("#ovAva").textContent = initials(p); $("#ovAva").style.background = avaBg(p.tg_id);
  $("#ovText").textContent = `Вы и ${p.first_name || "участник"} отметили друг друга. Бот уже прислал вам обоим контакты.`;
  $("#ovWrite").onclick = () => { $("#matchOv").hidden = true;
    if (p.username) { copy(`${p.first_name || ""}, привет! Мы совпали в Знакомствах Единения. Увидел(а), что ты ищешь: ${(p.seek || "").toLowerCase()}. Созвонимся?`); toast("Первое сообщение скопировано"); openTg(p.username); }
    else toast("У участника скрыт username, бот передал ему ваш контакт"); };
  $("#matchOv").hidden = false;
}
$("#ovClose").onclick = () => $("#matchOv").hidden = true;
function updBadge() { const b = $("#badge"); b.textContent = S.newMatches; b.hidden = !S.newMatches; $("#mBadge").textContent = S.newMatches ? ` · ${S.newMatches}` : ""; }
async function loadMatches() {
  try { const d = await api("/api/matches");
    $("#matchList").innerHTML = d.matches.length ? d.matches.map(m => `<div class="match"><div class="person"><div class="ava" style="background:${avaBg(m.tg_id)}">${esc(initials(m))}</div>
      <div class="t"><b>${esc(fullName(m))}</b><span>${esc(m.sphere)}</span></div></div>${m.username ? `<button class="btn sm" data-u="${esc(m.username)}">Написать</button>` : ""}</div>`).join("")
      : '<p class="empty-line">Пока нет взаимных знакомств. Отмечайте людей в ленте «Найди своих».</p>';
    $$("#matchList [data-u]").forEach(b => b.onclick = () => openTg(b.dataset.u));
    $("#likedYou").hidden = !d.liked_you;
    $("#likedYou").innerHTML = `<h3>Вас отметили еще ${d.liked_you}</h3><p class="sub">Имена откроются, если вы тоже отметите этих людей в ленте.</p>`;
  } catch (e) { fail(e); }
}
async function loadCoffee() {
  const box = $("#p-coffee");
  try { const c = await api("/api/coffee"); S.coffee = c;
    if (!c.pair) { box.innerHTML = `<div class="panel"><span class="eyebrow">Random Coffee</span><h3>Пара появится в понедельник</h3>
      <p class="sub">${!c.profile_done ? "Сначала заполните анкету в профиле: по ней подбирается пара." : !c.enabled ? "Вы выключили Random Coffee в анкете." : "Каждый понедельник в 10:00 бот подбирает вам человека по «ищу» и «могу помочь» и присылает его контакт."}</p></div>`;
      renderHomeCoffee(); return; }
    const p = c.pair, first = p.first_name || "Ваша пара";
    const msg = `${first}, привет! Нас свел Random Coffee в Единении. Я ${S.me.first_name || ""}, ${(S.me.sphere || "").toLowerCase()}. Давай созвонимся на 30 минут на этой неделе?`;
    box.innerHTML = `<div class="panel"><div class="steps" aria-hidden="true"><i class="on"></i><i class="on"></i><i class="${c.met != null ? "on" : ""}"></i></div>
      <div><span class="eyebrow">Неделя ${esc(c.week.split("-W")[1])}</span><h3 style="margin-top:8px">Ваша пара на эту неделю</h3></div>
      <div class="person"><div class="ava" style="background:${avaBg(p.tg_id)}">${esc(initials(p))}</div><div class="t"><b>${esc(fullName(p))}</b><span>${esc([p.sphere, p.city].filter(Boolean).join(" · "))}</span></div></div>
      <div class="why">${esc(c.reason)}</div>
      <div><p class="sub" style="margin-bottom:6px">Первое сообщение, можно поправить</p><textarea id="cMsg" rows="4">${esc(msg)}</textarea></div>
      ${p.username ? `<button class="btn" id="cWrite">Скопировать и написать</button>` : '<p class="sub">У участника скрыт username, бот передал ему ваш контакт.</p>'}</div>
      <div class="panel" id="fb">${c.met != null ? `<h3>Спасибо за отзыв</h3><p class="sub">${c.met ? "Баллы за встречу отправлены на подтверждение." : "Записали, что встреча не состоялась."}</p>`
      : `<h3>Созвонились?</h3><p class="sub">За встречу с отзывом начисляются баллы после подтверждения клуба.</p>
        <div class="btns" id="fbBtns"><button class="btn" id="fbYes">Да, созвонились</button><button class="btn ghost" id="fbNo">Не получилось</button></div>
        <div id="fbForm" hidden style="display:flex;flex-direction:column;gap:10px"><label class="f" for="fbText">ЧТО ЦЕННОГО ВЫНЕСЛИ<textarea id="fbText" rows="3"></textarea></label><button class="btn" id="fbSend">Отправить</button></div>`}</div>`;
    const w = $("#cWrite"); if (w) w.onclick = () => { copy($("#cMsg").value); toast("Сообщение скопировано"); openTg(p.username); };
    const y = $("#fbYes"); if (y) {
      y.onclick = () => { $("#fbBtns").hidden = true; $("#fbForm").hidden = false; $("#fbText").focus(); };
      $("#fbNo").onclick = async () => { await api(`/api/coffee/${c.id}/feedback`, {json: {met: false}}); loadCoffee(); };
      $("#fbSend").onclick = async () => { const t = $("#fbText").value.trim(); if (!t) { toast("Напишите пару слов о встрече"); return; }
        try { await api(`/api/coffee/${c.id}/feedback`, {json: {met: true, text: t}}); toast("Спасибо! Баллы ждут подтверждения"); loadCoffee(); refreshPoints(); } catch (e) { fail(e); } };
    }
    renderHomeCoffee();
  } catch (e) { fail(e); }
}
function renderHomeCoffee() {
  const c = S.coffee, el = $("#homeCoffee");
  if (!c || !c.pair) { el.innerHTML = `<div class="row2"><span>Random Coffee</span></div><p class="sub">Новая пара каждый понедельник. Чтобы попасть в подбор, заполните «ищу» и «могу помочь».</p><button class="btn ghost" data-tab="people" data-seg="coffee">Подробнее</button>`; return; }
  el.innerHTML = `<div class="row2"><span>Random Coffee на этой неделе</span></div>
    <div class="person"><div class="ava" style="background:${avaBg(c.pair.tg_id)}">${esc(initials(c.pair))}</div><div class="t"><b>${esc(fullName(c.pair))}</b><span>${esc([c.pair.sphere, c.pair.city].filter(Boolean).join(" · "))}</span></div></div>
    <button class="btn ghost" data-tab="people" data-seg="coffee">Открыть пару</button>`;
}

/* ---------- профиль ---------- */
function fillProfile() {
  const m = S.me;
  $("#meCard").innerHTML = `<div class="person"><div class="ava" style="background:${avaBg(m.tg_id)}">${esc(initials(m))}</div>
    <div class="t"><b>${esc(fullName(m))}</b><span>${m.level === "inside" ? "Inside-level" : "Club-level"}${m.paid_until ? " · до " + new Date(m.paid_until).toLocaleDateString("ru-RU", {day: "numeric", month: "long"}) : ""}</span></div></div>
    <div class="stats"><div class="stat"><b class="ptsv">${S.points ? S.points.balance : 0}</b><span>баллов</span></div><div class="stat"><b>${S.stats.matches}</b><span>знакомств</span></div><div class="stat"><b>${S.stats.coffee}</b><span>встреч</span></div></div>`;
  $("#insideCard").hidden = m.level === "inside";
  $("#pName").value = m.first_name || ""; $("#pSphere").value = m.sphere || ""; $("#pProject").value = m.project || ""; $("#pCity").value = m.city || "";
  $("#pSeek").value = m.seek || ""; $("#pGive").value = m.give || "";
  $("#pCoffee").setAttribute("aria-pressed", m.coffee ? "true" : "false"); $("#pOff").setAttribute("aria-pressed", m.offline ? "true" : "false");
}
$$(".toggle").forEach(t => t.onclick = () => t.setAttribute("aria-pressed", t.getAttribute("aria-pressed") === "true" ? "false" : "true"));
$("#saveProfile").onclick = async () => {
  const data = {first_name: $("#pName").value.trim(), sphere: $("#pSphere").value.trim(), project: $("#pProject").value.trim(), city: $("#pCity").value.trim(),
    seek: $("#pSeek").value.trim(), give: $("#pGive").value.trim(), coffee: $("#pCoffee").getAttribute("aria-pressed") === "true", offline: $("#pOff").getAttribute("aria-pressed") === "true"};
  try { await api("/api/me", {method: "PUT", json: data}); Object.assign(S.me, data); fillProfile(); toast("Анкета сохранена"); } catch (e) { fail(e); }
};
$("#toInside").onclick = () => { if (S.me.manager_username) openTg(S.me.manager_username); else toast("Менеджер пришлет условия перехода в Telegram"); };

/* ---------- первая анкета ---------- */
function showOnboard() {
  $("#onboard").hidden = false; const m = S.me;
  $("#oName").value = m.first_name || ""; $("#oSphere").value = m.sphere || ""; $("#oProject").value = m.project || ""; $("#oCity").value = m.city || "";
  $("#oSeek").value = m.seek || ""; $("#oGive").value = m.give || "";
  $("#oSave").onclick = async () => {
    const data = {first_name: $("#oName").value.trim(), sphere: $("#oSphere").value.trim(), project: $("#oProject").value.trim(), city: $("#oCity").value.trim(),
      seek: $("#oSeek").value.trim(), give: $("#oGive").value.trim(), offline: $("#oOff").getAttribute("aria-pressed") === "true", consent: $("#oConsent").checked};
    if (!data.consent) { toast("Отметьте согласие, чтобы войти"); return; }
    if (!data.sphere || !data.city || !data.seek || !data.give) { toast("Заполните сферу, город, «ищу» и «могу помочь»"); return; }
    try { await api("/api/me", {method: "PUT", json: data}); Object.assign(S.me, data, {consent_at: "1", profile_done: 1}); $("#onboard").hidden = true; start(); }
    catch (e) { fail(e); }
  };
}

/* ---------- запуск ---------- */
async function start() {
  $("#main").hidden = false; $("#tabs").hidden = false; $("#ptsPill").hidden = false;
  fillProfile();
  await Promise.allSettled([refreshPoints().then(fillProfile), loadEvents(), loadHomeLib(), loadFeed(), loadCoffee()]);
  route();
}
async function boot() {
  if (TG) { TG.ready(); TG.expand(); try { TG.setHeaderColor("#0A0D1A"); TG.setBackgroundColor("#0A0D1A"); } catch (e) {} }
  try {
    const d = await api("/api/me"); S.me = d.me; S.stats = d.stats; S.points = d.points; $("#gateJoin").href = d.join;
    $("#boot").hidden = true;
    if (d.me.status !== "active") {
      $("#gate").hidden = false;
      if (d.me.status === "expired") { $("#gateTitle").textContent = "Участие закончилось"; $("#gateText").textContent = "Продлите участие, и все ваши знакомства, баллы и материалы вернутся."; $("#gateJoin").textContent = "Продлить участие"; }
      return;
    }
    if (!d.me.consent_at || !d.me.profile_done) { showOnboard(); return; }
    start();
  } catch (e) {
    $("#boot").hidden = true; $("#gate").hidden = false;
    if (e.status === 401) { $("#gateTitle").textContent = "Откройте клуб через бота"; $("#gateText").textContent = "Приложение работает внутри Telegram: найдите @edinenie_club_bot и нажмите «Открыть клуб»."; $("#gateJoin").href = "https://t.me/edinenie_club_bot"; $("#gateJoin").textContent = "Перейти к боту"; }
    else { $("#gateTitle").textContent = "Не получилось загрузить"; $("#gateText").textContent = "Проверьте интернет и откройте приложение еще раз."; $("#gateJoin").hidden = true; }
  }
}
window.addEventListener("hashchange", route);
boot();
