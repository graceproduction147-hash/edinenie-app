/* Мини-приложение клуба Единение: все данные с сервера, вход через Telegram */
const TG = window.Telegram && window.Telegram.WebApp;
const DEV = new URLSearchParams(location.search).get("dev") || "";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const MONTHS = ["янв","февр","марта","апр","мая","июня","июля","авг","сент","окт","нояб","дек"];
const WD = ["Вс","Пн","Вт","Ср","Чт","Пт","Сб"];

let S = {evView:"list", calM:null, calDay:null, me:null, points:null, rules:[], shop:[], events:{soon:[],records:[]}, feed:[], filter:"all", newMatches:0};

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
function openPay(u) { u = u || "https://t.me/tribute/app?startapp=s14lC"; if (TG && TG.openTelegramLink && /^https:\/\/t\.me\//.test(u)) TG.openTelegramLink(u); else if (TG && TG.openLink) TG.openLink(u); else window.open(u, "_blank"); }
function haptic(type) { try { TG.HapticFeedback.impactOccurred(type || "light"); } catch (e) {} }

/* ---------- внешний вид ---------- */
(function logo() { let h = ""; for (let i = 0; i < 48; i++) { const a = i / 48 * Math.PI * 2, r1 = i % 2 ? 7 : 5, r2 = i % 2 ? 15 : 19;
  h += `<line x1="${20 + r1 * Math.cos(a)}" y1="${20 + r1 * Math.sin(a)}" x2="${20 + r2 * Math.cos(a)}" y2="${20 + r2 * Math.sin(a)}" stroke="currentColor" stroke-width=".7" stroke-linecap="round"/>`; }
  $("#logo").innerHTML = h; })();
const ORBS = [["#F2B394","#B0583F","#2A1218"],["#DCE6FF","#7189CF","#1A2140"],["#E8C9A0","#A0704A","#24170F"],["#E9B6C6","#9A4C6A","#24111C"],["#BFE0D0","#4E8C78","#0F1F1C"]];
const orb = id => { const o = ORBS[Math.abs(Number(id) || 0) % ORBS.length];
  return `radial-gradient(70% 60% at 82% 0%,${o[0]} 0%,${o[1]} 28%,transparent 62%),radial-gradient(90% 70% at 10% 110%,${o[2]} 0%,transparent 70%),#0F1224`; };
const stTag = p => p.level === "inside" ? `<em class="st">амбассадор</em>` : "";
const avaEl = p => `<div class="ava" style="background:${p.photo ? `url(/botpic/${esc(p.photo)}) center/cover` : avaBg(p.tg_id)}"></div>`;
const orbUrl = (id, s) => `/orb/${1000 + Math.abs(Number(id) || 0) % 1000}.png?v=2${s ? "&s=" + s : ""}`;
const avaBg = id => `#0b0d18 url(${orbUrl(id)}) center/cover`;
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
const TITLES = {home:["Клуб","Главная"], events:["Встречи и витрина","События"], lib:["Знания клуба","Библиотека"], people:["Круг","Люди"], profile:["Ваше участие","Профиль"]};
/* ---------- уровни Резидент и Амбассадор (внутри кода уровень Амбассадора по-прежнему называется inside) ---------- */
const LVL_NOTE = {
  home: null,
  events: ["эфиры, события партнеров, витрина предложений", "закрытые эфиры и их записи"],
  lib: ["открытые конспекты, подкасты, записи", "закрытые материалы"],
  people: ["рекомендации знакомств для всех участников", null],
  profile: ["награды Club", "награды только для Амбассадоров"]
};
function renderLvl(v) {
  const el = $("#lvl"), n = LVL_NOTE[v], inside = S.me && S.me.level === "inside";
  el.hidden = true; return; /* строка уровней под заголовком убрана: Inside отмечен замочками на самих карточках */
  if (!n) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<span class="c ${inside ? "" : "me"}">Club</span><span>${esc(n[0])}</span>` + (n[1] ? `<span class="c in ${inside ? "me" : ""}">Амбассадор</span><span>${esc(n[1])}</span>` : "")
    + `<button id="lvlMore">Что открывает статус Амбассадора</button>`;
  $("#lvlMore").onclick = levelsSheet;
}
function levelsSheet() {
  const amb = S.me && S.me.level === "inside", yr = !!S.year, n = S.norm;
  const items = n ? [["invite", "Привести друга в клуб", "Он должен оплатить участие"], ["story", "Два раза рассказать о клубе в сторис", `С хештегом #делюсь в чате клуба. Подтверждено: ${n.story_n || 0} из 2`], ["insight", "Написать инсайт после эфира", "С хештегом #инсайт в чате клуба"]] : [];
  const blk = (t, sub, items, mine, plus) => `<div class="lv${mine ? " mine" : ""}"><div class="lh"><b>${t}</b><span>${sub}</span>${mine ? "<em>у вас</em>" : ""}</div><ul>${items.map(i => `<li>${plus ? "+ " : ""}${i}</li>`).join("")}</ul></div>`;
  const grid = blk("Резидент", "по оплате", ["Жизнь клуба и чат", "Приложение и Random Coffee", "2 знакомства в месяц", "Скидки до 50% на события", "Место на витрине за приглашенного друга"], !amb && !yr)
    + blk("Амбассадор", "за вклад", ["4 знакомства в месяц", "Персональные знакомства", "Свой эфир в клубе", "Место на витрине на 1 месяц"], amb, true)
    + blk("Годовой тариф", "к любому уровню", ["Место на витрине на весь год", "Ментор клуба и своя рубрика", "2 гостевых пропуска на эфиры", "Выступление на сцене (вместе с Амбассадором)"], yr, true);
  openSheet(`<h3>Возможности клуба</h3>${grid}
    <div class="amb-how"><h4>Как стать Амбассадором</h4>${n ? `<p class="sub" style="margin:6px 0">${n.done ? `Статус действует еще ${n.days_left} дн. Чтобы сохранить, повторите три шага за ${n.days} дней.` : `Три шага за ${n.days} дней:`}</p><ul class="norm">${items.map(i => `<li class="${n[i[0]] ? "ok" : ""}"><i></i><div><b>${i[1]}</b><span>${n[i[0]] ? "Подтверждено командой" : i[2]}</span></div></li>`).join("")}</ul>` : ""}
      <div class="btns"><button class="btn sm" id="lvInv">Пригласить друга</button>${amb || yr ? '<button class="btn sm ghost" id="lvStream">Свой эфир</button>' : ""}${yr ? "" : '<button class="btn sm ghost" id="lvYear">Годовой тариф</button>'}</div></div>`,
    s => { const b = s.querySelector("#lvInv"); if (b) b.onclick = () => { const k = (S.rules || []).find(r => r.code === "invite"); if (k) { closeSheet(); taskSheet(k); } else toast("Ссылка загрузится через секунду, попробуйте еще раз"); };
      const st = s.querySelector("#lvStream"); if (st) st.onclick = () => { closeSheet(); ownStream(); };
      const y = s.querySelector("#lvYear"); if (y) y.onclick = () => { openPay((S.events && S.events.buy_url) || S.join); }; });
}
let _trk = {};
function track(k) {
  const t = Date.now(); if (_trk[k] && t - _trk[k] < 4000) return; _trk[k] = t;
  try { api("/api/track", {json: {kind: k}}).catch(() => {}); } catch (e) {}
}
function go(v, seg) {
  track("v_" + v + (seg ? "_" + seg : ""));
  $$("nav.tabs button").forEach(x => x.setAttribute("aria-selected", x.dataset.v === v ? "true" : "false"));
  $$(".view").forEach(x => x.classList.toggle("on", x.id === "v-" + v));
  $("#title").textContent = TITLES[v][1]; $(".pagehead").style.display = v === "home" ? "none" : "";
  if (v === "people") { peopleSeg("coffee"); }
  if (v === "events" && seg) evSeg(seg);
  if (v === "lib") loadLib();
  if (v === "profile") loadPerks();
  renderLvl(v);
  window.scrollTo(0, 0);
}
$(".pagehead").style.display = "none"; /* главная открыта по умолчанию */
$$("nav.tabs button").forEach(b => b.onclick = () => go(b.dataset.v));
$("#ptsPill").onclick = () => go("profile");
document.addEventListener("click", e => { const t = e.target.closest("[data-tab]"); if (t) go(t.dataset.tab, t.dataset.seg); });
function route() { const h = location.hash.slice(1);
  if (h === "coffee" || h === "matches") go("people", h); else if (h === "calendar") go("events", "soon"); else if (h === "offers") go("events", "off"); else if (TITLES[h]) go(h); }

/* ---------- баллы ---------- */
function setPoints(p) { S.points = p; }
async function refreshPoints() { const d = await api("/api/points"); S.rules = d.rules; S.shop = d.shop; S.invite = d.invite_link; S.claims = d.claims;
  setPoints({balance: d.balance, pending: d.pending}); renderTasks(); }

const HINTS = {insight: "Напишите в чате клуба с хештегом #инсайт или отправьте здесь", story: "Выложите сторис о клубе и напишите в чат с хештегом #делюсь", result: "Чего достигли благодаря клубу: напишите в чат с хештегом #замечаю", invite: "Баллы придут, когда друг оплатит участие: 50% от его первой оплаты"};
const hintOf = k => HINTS[k.code] || k.hint;
function renderTasks() {
  const pendingCodes = new Set((S.claims || []).filter(c => c.status === "pending").map(c => c.rule_code));
  const rules = S.rules.filter(r => r.code !== "coffee");
  renderLevels();
  if (!$("#tasks")) return;
  $("#tasks").innerHTML = rules.map(k => `<div class="task${pendingCodes.has(k.code) ? " done" : ""}"><div class="t"><b>${esc(k.title)} <span class="plus">+${k.points}</span></b><span>${esc(hintOf(k))}</span></div>
    <button class="btn sm" data-task="${esc(k.code)}">${pendingCodes.has(k.code) ? "Еще раз" : "Сделать"}</button></div>`).join("");
  $$("[data-task]").forEach(b => b.onclick = () => taskSheet(S.rules.find(k => k.code === b.dataset.task)));
}
function taskSheet(k, ref) {
  if (k.kind === "link") {
    openSheet(`<h3>${esc(k.title)}</h3><p class="sub">Ваша личная ссылка. Отправьте ее другу: когда он оплатит участие, это засчитается вам как шаг к статусу Амбассадора.</p>
      <div class="msg">${esc(S.invite)}</div><button class="btn" id="cp">Скопировать ссылку</button>`,
      s => s.querySelector("#cp").onclick = () => { copy(S.invite); toast("Ссылка скопирована"); closeSheet(); });
    return;
  }
  openSheet(`<h3>${esc(k.title)}</h3><p class="sub">${esc(k.hint)}. Команда клуба проверит и подтвердит.</p>
    ${k.kind === "file" ? '<label class="f" for="tf">СКРИНШОТ<input type="file" id="tf" accept="image/*"></label>' : ""}
    <label class="f" for="tx">${k.kind === "file" ? "КОММЕНТАРИЙ" : "ВАШ ТЕКСТ"}<textarea id="tx" rows="4"></textarea></label>
    <button class="btn" id="snd">Отправить на подтверждение</button>`, s => s.querySelector("#snd").onclick = async () => {
      const fd = new FormData(); fd.append("rule_code", k.code); fd.append("text", s.querySelector("#tx").value); if (ref) fd.append("ref", ref);
      const f = s.querySelector("#tf"); if (f && f.files[0]) fd.append("file", f.files[0]);
      if (k.kind === "file" && !(f && f.files[0])) { toast("Приложите скриншот"); return; }
      try { s.querySelector("#snd").disabled = true; await api("/api/claims", {body: fd}); closeSheet(); toast("Отправлено на подтверждение"); haptic("medium"); refreshPoints(); }
      catch (e) { s.querySelector("#snd").disabled = false; fail(e); }
    });
}
function renderShop() {}

/* ---------- эфиры ---------- */
async function loadEvents() { S.events = await api("/api/events"); renderEvents(); renderHero(); try { renderWeekAction(); } catch (e) {} }
function evRow(e) { const w = when(e.starts_at);
  return `<button class="item ev" data-ev="${e.id}">${e.cover ? `<img class="cvr row" src="${esc(e.cover)}" alt="" loading="lazy">` : ""}<div class="date"><b>${w.d}</b><span>${w.m}</span></div>
    <div class="t"><b>${esc(e.title)}</b><span>${w.wd}, ${w.t} · ${esc(e.rubric || "Эфир")} · ${esc(e.place)}</span></div>
    <div class="end">${e.locked ? `<span class="lock">${lockSVG}Амбассадор</span>` : e.going ? '<span class="going">Иду</span>' : ""}</div></button>`; }
function renderEvents() { renderFeed(); }
function feedItems() {
  const own = (S.events ? S.events.soon : []).map(e => ({k: String(e.starts_at).slice(0, 10), html: evRow(e), ev: e}));
  const par = (S.cal ? S.cal.items : []).map(e => ({k: e.date_from, html: calRow(e), cal: e}));
  return own.concat(par).sort((a, b) => a.k < b.k ? -1 : a.k > b.k ? 1 : 0);
}
function renderFeed() {
  const c = S.cal, items = feedItems();
  $("#evSoon").innerHTML = `<div class="list">${items.length ? items.map(x => x.html).join("") : '<p class="empty-line">Ближайшие события появятся здесь, как только команда их назначит.</p>'}</div>`;
  if (!$("#homeCal")) return;
  $("#homeCal").innerHTML = items.length ? `<div class="row2"><span>Ближайшие события</span></div>
    <div class="list">${items.slice(0, 3).map(x => x.html).join("")}</div>
    <button class="btn ghost" data-tab="events" data-seg="soon">Все события</button>` : "";
  $("#homeCal").hidden = !items.length;
  $$("[data-ev]").forEach(b => b.onclick = () => eventSheet(S.events.soon.find(e => e.id == b.dataset.ev)));
  $$("[data-cal]").forEach(b => b.onclick = () => calSheet(c.items.find(x => x.id == b.dataset.cal)));
  $$("[data-cv]").forEach(b => b.onclick = () => { S.evView = b.dataset.cv; renderFeed(); });
  $$("[data-cmove]").forEach(b => b.onclick = () => { const n = Number(b.dataset.cmove), t = S.calM.y * 12 + S.calM.m + n; S.calM = {y: Math.floor(t / 12), m: t % 12}; S.calDay = null; renderFeed(); });
  $$("[data-cmonth]").forEach(b => b.onclick = () => { S.calM.m = Number(b.dataset.cmonth); S.calDay = null; renderFeed(); });
  $$("[data-cday]").forEach(b => b.onclick = () => { S.calDay = S.calDay === b.dataset.cday ? null : b.dataset.cday; renderFeed(); });
  $$("[data-dayev]").forEach(b => b.onclick = () => eventSheet(S.events.soon.find(e => e.id == b.dataset.dayev)));
  $$("[data-daycal]").forEach(b => b.onclick = () => calSheet(c.items.find(x => x.id == b.dataset.daycal)));
}
const MFULL = ["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
const p2 = n => String(n).padStart(2, "0");
function calView() {
  const now = new Date(), tdy = `${now.getFullYear()}-${p2(now.getMonth() + 1)}-${p2(now.getDate())}`;
  if (!S.calM) S.calM = {y: now.getFullYear(), m: now.getMonth()};
  const {y, m} = S.calM, marks = (S.cal && S.cal.marks) || [], by = {}, perMonth = {};
  marks.forEach(x => { (by[x.d] = by[x.d] || []).push(x); if (x.d.slice(0, 4) == y) { const mi = Number(x.d.slice(5, 7)) - 1; (perMonth[mi] = perMonth[mi] || new Set()).add(x.k + x.id); } });
  const counts = MFULL.map((_, i) => perMonth[i] ? perMonth[i].size : 0), mx = Math.max(1, ...counts), total = counts.reduce((a, b) => a + b, 0);
  const tiles = MFULL.map((n, i) => `<button class="mt${i === m ? " cur" : ""}" data-cmonth="${i}" style="--k:${(counts[i] / mx).toFixed(2)}" aria-label="${n}: событий ${counts[i]}"><span>${MONTHS[i].slice(0, 3)}</span><b>${counts[i] || ""}</b></button>`).join("");
  const off = (new Date(y, m, 1).getDay() + 6) % 7, dim = new Date(y, m + 1, 0).getDate();
  let cells = "";
  for (let i = 0; i < off; i++) cells += "<i></i>";
  for (let d = 1; d <= dim; d++) { const k = `${y}-${p2(m + 1)}-${p2(d)}`, ms = by[k] || [], own = ms.some(z => z.own), n = new Set(ms.map(z => z.k + z.id)).size;
    cells += `<button class="cd${k === tdy ? " today" : ""}${k === S.calDay ? " sel" : ""}${n ? " has" : ""}${own ? " own" : ""}" data-cday="${k}" ${n ? "" : "tabindex='-1'"}><span>${d}</span>${n ? `<em>${n > 1 ? n : ""}</em>` : ""}</button>`; }
  let det = "";
  if (S.calDay) { const ms = by[S.calDay] || [], seen = new Set(), rows = [];
    ms.forEach(z => { const key = z.k + z.id; if (seen.has(key)) return; seen.add(key);
      const up = z.k === "ev" ? (S.events && S.events.soon.find(e => e.id == z.id)) : (S.cal && S.cal.items.find(e => e.id == z.id));
      rows.push(up ? (z.k === "ev" ? evRow(up).replace("data-ev=", "data-dayev=") : calRow(up).replace("data-cal=", "data-daycal=")) : `<div class="item"><div class="t"><b>${esc(z.t)}</b><span>${z.own ? "Клуб" : "Партнер"} · прошло</span></div></div>`); });
    const p = S.calDay.split("-").map(Number);
    det = `<p class="sub" style="margin-top:14px">${p[2]} ${MFULL[p[1] - 1].toLowerCase().replace(/ь$/, "я").replace(/т$/, "та").replace(/й$/, "я")}</p><div class="list">${rows.length ? rows.join("") : '<p class="empty-line">В этот день ничего не запланировано.</p>'}</div>`; }
  return `<div class="cal"><div class="row2 ch"><button class="nav" data-cmove="-12" aria-label="Предыдущий год">&#8249;&#8249;</button><span>Год <b>${y}</b> · событий ${total}</span><button class="nav" data-cmove="12" aria-label="Следующий год">&#8250;&#8250;</button></div>
    <div class="mtiles">${tiles}</div>
    <div class="row2 ch" style="margin-top:18px"><button class="nav" data-cmove="-1" aria-label="Предыдущий месяц">&#8249;</button><b class="mn">${MFULL[m]}</b><button class="nav" data-cmove="1" aria-label="Следующий месяц">&#8250;</button></div>
    <div class="grid7 wdh"><span>пн</span><span>вт</span><span>ср</span><span>чт</span><span>пт</span><span>сб</span><span>вс</span></div>
    <div class="grid7">${cells}</div>
    <p class="sub legend"><i class="own"></i>эфиры и события клуба <i class="par"></i>события партнеров</p>${det}</div>`; }
function renderHero() {
  const e = S.events.soon[0];
  if (!e) { $("#heroBox").innerHTML = ""; return; }
  const w = when(e.starts_at);
  $("#heroBox").innerHTML = `<div class="panel nx">${e.cover ? `<img class="cvr" src="${esc(e.cover)}" alt="">` : ""}<div class="t"><span class="eyebrow">Ближайший эфир · ${w.wd} ${w.d} ${w.m}, ${w.t}</span><b>${esc(e.title)}</b></div><button class="btn sm" id="heroGo">${e.locked ? "Для Амбассадоров" : e.going ? "Вы идете" : "Буду"}</button></div>`;
  $("#heroGo").onclick = () => eventSheet(e);
}
function eventSheet(e) { const w = when(e.starts_at);
  openSheet(`${e.cover ? `<img class="cvr big" src="${esc(e.cover)}" alt="${esc(e.title)}">` : ""}<p class="sub">${w.wd}, ${w.d} ${w.m} · ${w.t} МСК · ${esc(e.place)}</p><h3>${esc(e.title)}</h3>
    <div class="tags">${e.rubric ? `<span class="tag">${esc(e.rubric)}</span>` : ""}${e.speaker ? `<span class="tag">${esc(e.speaker)}</span>` : ""}${e.inside_only ? `<span class="lock">${lockSVG}Амбассадор-level</span>` : ""}</div>
    ${e.description ? `<p style="margin:0">${esc(e.description)}</p>` : ""}
    ${e.locked ? '<p class="sub">Закрытое событие для Амбассадоров. Как им стать, написано в разделе «Профиль».</p>'
      : `<p class="sub">${e.going ? "Вы записаны. Бот напомнит за день и за час." : "Отметьтесь, и бот пришлет ссылку и напомнит о начале. После эфира оставьте инсайт: он засчитает участие и даст баллы."}</p>
        ${e.going && e.join_url ? `<a class="btn" href="${esc(e.join_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Подключиться</a>` : ""}
        <button class="btn ${e.going ? "ghost" : ""}" id="eg">${e.going ? "Не смогу прийти" : "Буду"}</button>
        ${S.year && e.going ? `<button class="btn ghost" id="gst" ${S.events.guest.left < 1 ? "disabled" : ""}>${S.events.guest.left < 1 ? "Гостевые пропуска закончились" : `Позвать друга гостем (осталось ${S.events.guest.left})`}</button>` : ""}`}`,
    s => { const gb = s.querySelector("#gst"); if (gb) gb.onclick = () => guestSheet(e);
      const b = s.querySelector("#eg"); if (b) b.onclick = async () => {
      try { const r = await api(`/api/events/${e.id}/rsvp`, {method: "POST"}); e.going = r.going; e.join_url = r.join_url; toast(r.going ? "Отлично, бот напомнит" : "Отметка снята"); renderEvents(); renderHero(); if (S.year && r.going) eventSheet(e); else closeSheet(); haptic(); }
      catch (err) { fail(err); } }; });
}
function guestSheet(e) {
  openSheet(`<h3>Гость на эфир</h3><p class="sub">${esc(e.title)}. Бонус годового тарифа: друг приходит бесплатно. Напишите его имя, и команда будет знать, кого ждать.</p>
    <label class="f" for="gsN">ИМЯ ДРУГА<input type="text" id="gsN" maxlength="80"></label>
    <button class="btn" id="gsGo">Отправить</button>`,
    s => s.querySelector("#gsGo").onclick = async () => {
      const btn = s.querySelector("#gsGo"); btn.disabled = true;
      try { const r = await api(`/api/events/${e.id}/guest`, {method: "POST", json: {name: s.querySelector("#gsN").value}});
        S.events.guest.left = r.left; renderPerks();
        openSheet(`<h3>Готово</h3><p class="sub">Гость записан. Отправьте другу ссылку на эфир${r.join_url ? "" : ": команда пришлет ее в Telegram"}. Осталось пропусков: ${r.left}.</p>
          ${r.join_url ? `<div class="msg">${esc(r.join_url)}</div><button class="btn" id="gsCp">Скопировать ссылку</button>` : ""}`,
          s2 => { const c = s2.querySelector("#gsCp"); if (c) c.onclick = () => { copy(r.join_url); toast("Ссылка скопирована"); }; }); }
      catch (err) { btn.disabled = false; fail(err); } });
}
/* «За 60 секунд»: главное из эфира карточками, как сторис */
const S60_BG = ["radial-gradient(circle at 85% 10%,#e8704866,transparent 55%),radial-gradient(circle at 5% 90%,#5a6ee555,transparent 55%),#10122a",
  "radial-gradient(circle at 10% 15%,#d6608a55,transparent 55%),radial-gradient(circle at 90% 85%,#46a0e855,transparent 55%),#0f1528",
  "radial-gradient(circle at 80% 20%,#f0964666,transparent 55%),radial-gradient(circle at 15% 85%,#3caac855,transparent 55%),#0c1828",
  "radial-gradient(circle at 15% 10%,#b464f055,transparent 55%),radial-gradient(circle at 85% 90%,#f0786455,transparent 55%),#16102c"];
function storyViewer(r) {
  const ideas = r.summary || []; if (!ideas.length) return;
  const cards = [{k: "За 60 секунд", t: r.title, s: r.speaker}].concat(ideas.map((t, i) => ({k: `${i + 1} из ${ideas.length}`, t}))), N = cards.length, DUR = 7000;
  let i = 0, timer = null;
  const ov = document.createElement("div"); ov.id = "s60v";
  document.body.appendChild(ov);
  const close = () => { clearTimeout(timer); ov.remove(); };
  const show = n => {
    clearTimeout(timer); i = Math.max(0, Math.min(N - 1, n)); const c = cards[i], last = i === N - 1;
    ov.style.background = S60_BG[i % S60_BG.length];
    ov.innerHTML = `<div class="bars">${cards.map((_, j) => `<span class="${j < i ? "done" : j === i ? "cur" : ""}"><i ${j === i && !last ? `style="animation-duration:${DUR}ms"` : ""}></i></span>`).join("")}</div>
      <button class="qx" aria-label="Закрыть">&#10005;</button>
      <div class="zone l"></div><div class="zone r"></div>
      <div class="body"><span class="eyebrow">${esc(c.k)}</span><p class="${i === 0 ? "ttl" : ""}">${esc(c.t)}</p>${c.s ? `<span class="sp">${esc(c.s)}</span>` : ""}
        ${last ? `<div class="end">${r.recording_url ? `<a class="btn solid" href="${esc(r.recording_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Смотреть запись</a>` : ""}<button class="btn ghost" id="s60i">Оставить инсайт</button></div>` : ""}</div>`;
    ov.querySelector(".qx").onclick = close;
    ov.querySelector(".zone.l").onclick = () => show(i - 1);
    ov.querySelector(".zone.r").onclick = () => last ? close() : show(i + 1);
    const ib = ov.querySelector("#s60i"); if (ib) ib.onclick = () => { close(); taskSheet(S.rules.find(k => k.code === "insight"), "event:" + r.id); };
    if (!last) timer = setTimeout(() => show(i + 1), DUR);
  };
  show(0); track("s60");
}
function recSheet(r) { const w = when(r.starts_at);
  const ideas = r.summary || [], ts = r.timecodes || [];
  openSheet(`${r.cover ? `<img class="cvr big" src="${esc(r.cover)}" alt="${esc(r.title)}">` : ""}<p class="sub">${esc(r.speaker)} · ${w.d} ${w.m}</p><h3>${esc(r.title)}</h3>
    ${r.locked ? '<p class="sub">Запись доступна Амбассадорам.</p>' : `
    ${ideas.length ? `<button class="btn solid" id="s60">За 60 секунд · ${ideas.length} ${ideas.length === 1 ? "мысль" : ideas.length < 5 ? "мысли" : "мыслей"}</button>` : ""}
    <div class="btns">${r.recording_url ? `<a class="btn sm" id="recGo" href="${esc(r.recording_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Смотреть запись</a>` : ""}
      ${r.podcast_url ? `<a class="btn sm ghost" href="${esc(r.podcast_url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Слушать подкастом</a>` : ""}</div>
    ${ideas.length ? `<div><p class="sub" style="margin-bottom:6px">Главное из эфира</p><ul>${ideas.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>` : ""}
    ${ts.length ? `<div><p class="sub" style="margin-bottom:6px">Таймкоды</p><div class="ts">${ts.map(t => `<div><b>${esc(t[0])}</b><span>${esc(t[1])}</span></div>`).join("")}</div></div>` : ""}
    <div class="switch"><span>Смотрел(а) этот эфир</span><button class="toggle" id="recW" aria-pressed="${r.watched ? "true" : "false"}" aria-label="Смотрел(а) этот эфир"></button></div>
    <button class="btn" id="ins">Оставить инсайт</button>`}`,
    s => {
      const w = s.querySelector("#recW"), setW = async on => { try { await api(`/api/events/${r.id}/watch`, {json: {on}}); r.watched = on; if (w) w.setAttribute("aria-pressed", on ? "true" : "false"); renderWeekAction(); } catch (e) { fail(e); } };
      if (w) w.onclick = () => setW(w.getAttribute("aria-pressed") !== "true");
      const s6 = s.querySelector("#s60"); if (s6) s6.onclick = () => { closeSheet(); storyViewer(r); };
      const go = s.querySelector("#recGo"); if (go) go.addEventListener("click", () => { if (!r.watched) setW(true); });
      const b = s.querySelector("#ins"); if (b) b.onclick = () => taskSheet(S.rules.find(k => k.code === "insight"), "event:" + r.id); });
}
function evSeg(k) { $$("[data-es]").forEach(x => x.setAttribute("aria-pressed", x.dataset.es === k ? "true" : "false"));
  $("#evSoon").hidden = k !== "soon"; $("#evOff").hidden = k !== "off"; if (k === "off") loadOffers(); }
$$("[data-es]").forEach(b => b.onclick = () => evSeg(b.dataset.es));

/* ---------- календарь событий ---------- */
async function loadCal() { try { S.cal = await api("/api/calendar"); renderFeed(); } catch (e) { S.cal = null; } }
function calDay(s) { const p = String(s).split("-").map(Number); return {d: String(p[2]).padStart(2, "0"), m: MONTHS[p[1] - 1]}; }
function calRow(e) { const w = calDay(e.date_from);
  return `<button class="item" data-cal="${e.id}"><div class="date"><b>${w.d}</b><span>${w.m}</span></div>
    <div class="t"><b>${esc((e.icon ? e.icon + " " : "") + e.title)}</b><span>${esc([e.own ? "Клуб" : "Партнер", e.when_text, e.place].filter(Boolean).join(" · "))}</span></div>
    <div class="end">${e.promo || e.perk ? '<span class="going">Скидка</span>' : ""}</div></button>`; }
function calSheet(e) {
  openSheet(`<p class="sub">${esc([e.when_text, e.place].filter(Boolean).join(" · "))}</p><h3>${esc((e.icon ? e.icon + " " : "") + e.title)}</h3>
    ${e.body ? `<div style="white-space:pre-wrap;font-size:15px;margin-bottom:12px">${esc(e.body)}</div>` : ""}
    ${e.perk || e.promo ? `<div class="panel"><p style="margin:0 0 6px"><b>Для участников клуба</b></p>${e.perk ? `<p class="sub" style="margin:0 0 8px">${esc(e.perk)}</p>` : ""}
      ${e.promo ? `<div class="row2"><span>Промокод <b>${esc(e.promo)}</b></span><button class="btn sm ghost" id="cpPromo">Скопировать</button></div>` : ""}</div>` : ""}
    ${e.link ? `<a class="btn" href="${esc(e.link)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Подробности и регистрация</a>` : ""}
    ${e.contact ? `<button class="btn ghost" id="cTg">Подробнее у ${esc(e.contact)}</button>` : ""}`,
    s => { const p = s.querySelector("#cpPromo"); if (p) p.onclick = () => { copy(e.promo); toast("Промокод скопирован"); };
      const t = s.querySelector("#cTg"); if (t) t.onclick = () => openTg(e.contact); });
}

/* ---------- библиотека ---------- */
let libType = "all", libTimer, libPillar = "env";
const LIBP = [["env", "Окружение"], ["game", "Большая игра"], ["state", "Состояние"]];
const inPillar = x => (x.pillar || "env") === libPillar;
$("#libPills").innerHTML = LIBP.map(([k, v]) => `<button class="chip" data-lp="${k}" aria-pressed="${k === libPillar}">${v}</button>`).join("");
$$("[data-lp]").forEach(c => c.onclick = () => { libPillar = c.dataset.lp; $$("[data-lp]").forEach(x => x.setAttribute("aria-pressed", x === c ? "true" : "false")); loadLib(); });
$("#libSearch").oninput = () => { clearTimeout(libTimer); libTimer = setTimeout(loadLib, 300); };
const orbImg = seed => `<img class="orb" src="/orb/${(seed % 2000 + 2000) % 2000}.png?v=2" alt="" loading="lazy">`;
const fullSp = s => s === "Влад" ? "Влад Митьковский" : s;
function recWhen(iso) { try { const p = new Intl.DateTimeFormat("ru-RU", {day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow"}).format(new Date(iso)); return p.replace(" в ", ", "); } catch (e) { return ""; } }
const recSub = r => [fullSp(r.speaker), recWhen(r.starts_at)].filter(Boolean).join(" · ");
const libItem = x => `<button class="item" data-lib="${x.id}">${orbImg(x.event_id || x.id + 500)}
  <div class="t"><b>${esc(x.title)}</b><span>${esc((() => { const ev = x.event_id && S.events && S.events.records.find(r => r.id == x.event_id); return ev ? recSub(ev) : [x.type === "rec" ? "" : TYPE[x.type], fullSp(x.author), x.meta].filter(Boolean).join(" · "); })())}</span></div>
  <div class="end">${x.locked ? `<span class="lock">${lockSVG}Амбассадор</span>` : ""}</div></button>`;
function bindLib(root, items) { root.querySelectorAll("[data-lib]").forEach(b => b.onclick = () => libSheet(items.find(x => x.id == b.dataset.lib))); }
async function loadLib() {
  try { const items = (await api(`/api/library?type=${libType}&q=${encodeURIComponent($("#libSearch").value)}`)).filter(x => { const ev = x.event_id && S.events && S.events.records.find(r => r.id == x.event_id); return inPillar(ev && ev.pillar ? ev : x); });
    const q = $("#libSearch").value.trim().toLowerCase();
    const recs = (S.events && (libType === "all" || libType === "rec")) ? S.events.records.filter(inPillar).filter(r => !items.some(x => x.event_id == r.id) && (!q || (r.title + " " + r.speaker).toLowerCase().includes(q))) : [];
    const recRow = r => `<button class="item" data-rec="${r.id}">${orbImg(r.id)}
      <div class="t"><b>${esc(r.title)}</b><span>${esc(recSub(r))}</span></div><div class="end">${r.locked ? `<span class="lock">${lockSVG}Амбассадор</span>` : ""}</div></button>`;
    $("#libList").innerHTML = ((recs.length || items.length) ? recs.map(recRow).join("") + items.map(libItem).join("") : '<p class="empty-line">В этом разделе пока пусто.</p>')
      + `<button class="btn ghost" id="libStream" style="margin-top:10px">Провести эфир в клубе</button>`;
    $("#libStream").onclick = ownStream;
    $$("#libList [data-rec]").forEach(b => b.onclick = () => recSheet(recs.find(r => r.id == b.dataset.rec)));
    bindLib($("#libList"), items); } catch (e) { fail(e); }
}
async function loadHomeLib() { const items = (await api("/api/library")).slice(0, 3);
  if (!$("#homeLib")) return;
  $("#homeLib").innerHTML = items.length ? items.map(libItem).join("") : '<p class="empty-line">Первые материалы появятся после эфиров клуба.</p>'; bindLib($("#homeLib"), items); }
function libSheet(x) {
  openSheet(`<p class="sub">${esc([TYPE[x.type], x.author, x.meta].filter(Boolean).join(" · "))}</p><h3>${esc(x.title)}</h3>
    ${x.locked ? '<p class="sub">Материал открыт Амбассадорам.</p>'
      : `${x.body ? `<div style="white-space:pre-wrap;font-size:15px">${esc(x.body)}</div>` : ""}
         ${x.url ? `<a class="btn" href="${esc(x.url)}" target="_blank" rel="noopener" style="text-align:center;text-decoration:none">Открыть</a>` : ""}`}`);
}

/* ---------- предложения участников ---------- */
async function loadOffers() { try { const d = await api("/api/offers"); S.offers = d.items; S.slots = d.slots; S.offerDays = d.days; renderOffers(); } catch (e) { fail(e); } }
function offerRow(o) {
  return `<button class="item" data-off="${o.id}"><div class="t"><b>${esc(o.title)}</b>
    <span>${esc([o.author, o.sphere].filter(Boolean).join(" · "))}</span>
    <span>${esc([o.price, o.barter ? "открыт к бартеру" : ""].filter(Boolean).join(" · "))}</span></div>
    <div class="end">${o.status === "pending" ? '<span class="lock">на проверке</span>' : o.status === "expired" ? '<span class="lock">срок закончился</span>' : o.mine ? '<span class="going">Мое</span>' : ""}</div></button>`;
}
function renderOffers() {
  const all = S.offers || [], mine = all.filter(o => o.mine), rest = all.filter(o => !o.mine && o.status === "active");
  const sl = S.slots || {free: 0, invited: 0}, can = (S.me && S.me.level === "inside") || !!S.year || sl.free > 0;
  $("#evOff").innerHTML = `<p class="sub">Участники и партнеры клуба предлагают свои услуги и продукты по специальной цене или в обмен. Выберите предложение и отправьте заявку: автор получит ее в Telegram.</p>
    ${can ? `<button class="btn" id="offNew">${sl.free > 0 ? "Опубликовать свое предложение" : "Получить место: пригласить друга"}</button>` : ""}
    ${mine.length ? `<h2 class="sec">Мои предложения</h2><div class="list">${mine.map(offerRow).join("")}</div>` : ""}
    ${rest.length ? `<div class="list">${rest.map(offerRow).join("")}</div>` : ""}`;
  const on_ = $("#offNew"); if (on_) on_.onclick = () => { if (sl.free > 0) newOfferSheet(); else taskSheet(S.rules.find(k => k.code === "invite")); };
  $$("[data-off]").forEach(b => b.onclick = () => offerSheet(all.find(o => o.id == b.dataset.off)));
}
function offerSheet(o) {
  openSheet(`<p class="sub">${esc([o.author, o.sphere, o.city].filter(Boolean).join(" · "))}</p><h3>${esc(o.title)}</h3>
    <div style="white-space:pre-wrap;font-size:15px;margin-bottom:12px">${esc(o.body)}</div>
    ${o.price ? `<div class="panel"><p style="margin:0"><b>Для участников клуба:</b> ${esc(o.price)}</p></div>` : ""}
    ${o.barter ? `<div class="panel"><p style="margin:0"><b>Открыт к бартеру.</b>${o.barter_for ? " Интересно: " + esc(o.barter_for) : ""}</p></div>` : ""}
    ${o.mine ? `<p class="sub">${o.status === "pending" ? "Предложение на проверке у команды клуба. После одобрения оно появится у всех на месяц." : o.status === "expired" ? (o.year ? "Годовой тариф закончился, и место на витрине закрыто. Продлите год или пригласите друга." : "Месяц размещения закончился. Чтобы разместить снова, пригласите друга.") : "Это ваше предложение" + (o.until ? ", оно на витрине до " + calDay(o.until).d + " " + calDay(o.until).m : o.year ? ", оно на витрине, пока вы на годовом тарифе" : "") + ". Заявки придут вам в Telegram."}</p><button class="btn ghost" id="offDel">Убрать предложение</button>`
      : `${o.price ? `<button class="btn" id="offBuy" ${o.asked_buy ? "disabled" : ""}>${o.asked_buy ? "Заявка отправлена" : "Купить по специальной цене"}</button>` : ""}
         ${o.barter ? `<button class="btn ghost" id="offBar" ${o.asked_barter ? "disabled" : ""}>${o.asked_barter ? "Предложение обмена отправлено" : "Предложить бартер"}</button>` : ""}`}`,
    s => { const b = s.querySelector("#offBuy"); if (b) b.onclick = () => requestSheet(o, "buy");
      const r = s.querySelector("#offBar"); if (r) r.onclick = () => requestSheet(o, "barter");
      const d = s.querySelector("#offDel"); if (d) d.onclick = async () => { try { await api("/api/offers/" + o.id, {method: "DELETE"}); closeSheet(); toast("Предложение убрано"); loadOffers(); } catch (e) { fail(e); } }; });
}
function requestSheet(o, kind) {
  openSheet(`<h3>${kind === "buy" ? "Заявка на покупку" : "Предложить бартер"}</h3>
    <p class="sub">${esc(o.title)}. Автор получит заявку в Telegram и напишет вам напрямую.</p>
    <label class="f" for="rqMsg">${kind === "buy" ? "СООБЩЕНИЕ (НЕОБЯЗАТЕЛЬНО)" : "ЧТО МОЖЕТЕ ПРЕДЛОЖИТЬ ВЗАМЕН"}<textarea id="rqMsg" rows="4"></textarea></label>
    <button class="btn" id="rqGo">Отправить заявку</button>`,
    s => s.querySelector("#rqGo").onclick = async () => {
      const btn = s.querySelector("#rqGo"); btn.disabled = true;
      try { await api(`/api/offers/${o.id}/request`, {method: "POST", json: {kind, message: s.querySelector("#rqMsg").value}}); closeSheet(); toast("Заявка отправлена автору"); haptic("medium"); loadOffers(); }
      catch (e) { btn.disabled = false; fail(e); } });
}
function newOfferSheet() {
  openSheet(`<h3>Ваше предложение клубу</h3>
    <p class="sub">Услуга или продукт по специальной цене для участников, либо обмен. Команда клуба проверит предложение до публикации, на витрине оно проведет месяц.</p>
    <label class="f" for="ofT">НАЗВАНИЕ<input type="text" id="ofT" maxlength="100"></label>
    <label class="f" for="ofB">ЧТО ВЫ ПРЕДЛАГАЕТЕ<textarea id="ofB" rows="4" maxlength="800"></textarea></label>
    <label class="f" for="ofP">СПЕЦИАЛЬНАЯ ЦЕНА ДЛЯ КЛУБА<input type="text" id="ofP" maxlength="120" placeholder="например, 5 000 вместо 7 000"></label>
    <div class="row2"><span>Открыт к бартеру</span><button class="toggle" id="ofBar" aria-pressed="false"></button></div>
    <label class="f" for="ofF" id="ofFw" hidden>НА ЧТО ИНТЕРЕСЕН ОБМЕН<textarea id="ofF" rows="2" maxlength="300"></textarea></label>
    <button class="btn" id="ofGo">Отправить на проверку</button>`,
    s => { const t = s.querySelector("#ofBar");
      t.onclick = () => { const on = t.getAttribute("aria-pressed") !== "true"; t.setAttribute("aria-pressed", on ? "true" : "false"); s.querySelector("#ofFw").hidden = !on; };
      s.querySelector("#ofGo").onclick = async () => {
        const btn = s.querySelector("#ofGo"); btn.disabled = true;
        try { await api("/api/offers", {method: "POST", json: {title: s.querySelector("#ofT").value, body: s.querySelector("#ofB").value, price: s.querySelector("#ofP").value,
              barter: t.getAttribute("aria-pressed") === "true", barter_for: s.querySelector("#ofF").value}});
          closeSheet(); toast("Отправлено на проверку"); loadOffers(); }
        catch (e) { btn.disabled = false; fail(e); } }; });
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
  <div class="cover" style="background:${p.photo ? `linear-gradient(180deg,rgba(0,0,0,.05) 40%,rgba(0,0,0,.6)),url(/botpic/${esc(p.photo)}) center/cover` : `#0b0d18 url(${orbUrl(p.tg_id, 480)}) center/cover`}"><div class="who"><b>${esc(fullName(p))}</b><span>${esc([p.sphere, p.city].filter(Boolean).join(" · "))}</span></div>
  ${top ? '<span class="stamp yes">Знакомимся</span><span class="stamp no">Дальше</span>' : ""}</div>
  <div class="body">${parseTags(p.tags).length ? `<div class="tags">${parseTags(p.tags).slice(0, 4).map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}${p.project ? `<div class="r"><span class="lbl">Проект</span><p>${esc(p.project)}</p></div>` : ""}
   <div class="r"><span class="lbl">Ищет</span><p>${esc(p.seek)}</p></div><div class="r"><span class="lbl">Может помочь</span><p>${esc(p.give)}</p></div>
   <div class="tags"><span class="tag">${p.level === "inside" ? "амбассадор" : "резидент"}</span>${p.offline ? '<span class="tag">офлайн</span>' : ""}</div></div></article>`;
function renderDeck() {
  const d = $("#deck");
  if (!S.feed.length) { d.innerHTML = `<div class="empty"><h3>Вы посмотрели всех</h3><p>Новые участники появятся после вступления в клуб, бот пришлет уведомление.</p></div>`; return; }
  d.innerHTML = S.feed.slice(0, 2).reverse().map((p, i, a) => cardHTML(p, i === a.length - 1)).join("");
  bindDrag(d.querySelector(".card:not(.back)"));
}
function bindDrag(el) {
  // Тянем карточку только когда жест явно горизонтальный: вертикальный жест остается за прокруткой текста внутри карточки.
  let x0 = 0, y0 = 0, dx = 0, dy = 0, down = false, drag = false; const yes = el.querySelector(".stamp.yes"), no = el.querySelector(".stamp.no");
  el.onpointerdown = e => { down = true; drag = false; dx = 0; dy = 0; x0 = e.clientX; y0 = e.clientY; };
  el.onpointermove = e => { if (!down) return; dx = e.clientX - x0; dy = e.clientY - y0;
    if (!drag) { if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.6) { drag = true; try { el.setPointerCapture(e.pointerId); } catch (x) {} el.classList.add("dragging"); } else return; }
    el.style.transform = `translate(${dx}px,0) rotate(${dx / 22}deg)`;
    yes.style.opacity = Math.max(0, Math.min(1, dx / 90)); no.style.opacity = Math.max(0, Math.min(1, -dx / 90)); };
  const end = () => { if (!down) return; down = false; const was = drag; drag = false; el.classList.remove("dragging");
    if (was && dx > 100) decide(true); else if (was && dx < -100) decide(false); else { el.style.transform = ""; yes.style.opacity = 0; no.style.opacity = 0; } dx = 0; };
  el.onpointerup = end; el.onpointercancel = end;
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
  $("#ovMe").textContent = ""; $("#ovMe").style.background = avaBg(S.me.tg_id);
  $("#ovAva").textContent = ""; $("#ovAva").style.background = avaBg(p.tg_id);
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
    $("#matchList").innerHTML = d.matches.length ? d.matches.map(m => `<div class="match"><div class="person"><div class="ava" style="background:${avaBg(m.tg_id)}"></div>
      <div class="t"><b>${esc(fullName(m))}</b><span>${esc(m.sphere)}</span></div></div>${m.username ? `<button class="btn sm" data-u="${esc(m.username)}">Написать</button>` : ""}</div>`).join("")
      : '<p class="empty-line">Пока нет взаимных знакомств. Отмечайте людей в ленте «Найди своих».</p>';
    $$("#matchList [data-u]").forEach(b => b.onclick = () => openTg(b.dataset.u));
    $("#likedYou").hidden = !d.liked_you;
    $("#likedYou").innerHTML = `<h3>Вас отметили еще ${d.liked_you}</h3><p class="sub">Имена откроются, если вы тоже отметите этих людей в ленте.</p>`;
  } catch (e) { fail(e); }
}
async function loadCoffee() {
  // Рекомендации знакомств на месяц (раньше здесь был Random Coffee; имя функции оставлено, чтобы не трогать остальной код)
  const box = $("#p-coffee");
  try { const c = await api("/api/recs"); S.coffee = c;
    if (!c.items.length) {
      box.innerHTML = `<div class="panel"><h3>Рекомендации появятся позже</h3>
      <p class="sub">${!c.profile_done ? "Сначала заполните анкету в профиле: по ней подбираются люди." : !c.enabled ? "Вы выключили рекомендации в профиле." : "Пока нет подходящих людей. Загляните позже, когда в клубе станет больше участников."}</p></div>`;
      renderHomeCoffee(); return; }
    box.innerHTML = 
      c.items.map(p => {
        const msg = `${p.first_name || ""}, привет! Я ${S.me.first_name || ""}, ${(S.me.sphere || "").toLowerCase()}. Увидел(а) вас в Единении и хочу познакомиться. Давайте созвонимся на 20 минут?`;
        return `<div class="panel" data-rec="${p.id}">
        <div class="person">${avaEl(p)}<div class="t"><b>${esc(fullName(p))} ${stTag(p)}</b><span>${esc([p.sphere, p.city].filter(Boolean).join(" · "))}</span></div></div>
        ${p.project ? `<div class="r"><span class="lbl">Проект</span><p>${esc(p.project)}</p></div>` : ""}
        <div class="r"><span class="lbl">Ищет</span><p>${esc(p.seek || "Не указано")}</p></div><div class="r"><span class="lbl">Может помочь</span><p>${esc(p.give || "Не указано")}</p></div>
        <div class="why">${esc(p.reason)}</div>
        <button class="btn${p.written ? " ghost" : ""}" data-w="${p.id}" data-u="${esc(p.username || "")}" data-m="${esc(msg)}">${p.written ? "Написать еще раз" : "Написать"}</button></div>`; }).join("") +
      `<div class="panel"><h3>Написали людям?</h3><p class="sub">Нажмите «Обновить», когда напишете. Мы спросим, как прошло, и подберем новых людей.</p>
        <button class="btn" id="recRefresh"${c.can_refresh ? "" : " disabled"}>Обновить</button>${c.can_refresh ? "" : '<p class="hint">Станет доступна после первого «Написать».</p>'}</div>`;
    $$("#p-coffee [data-w]").forEach(b => b.onclick = async () => {
      copy(b.dataset.m); toast("Сообщение скопировано"); openTg(b.dataset.u);
      try { await api(`/api/recs/${b.dataset.w}/written`, {json: {}}); const r = $("#recRefresh"); if (r) r.disabled = false; b.textContent = "Написать еще раз"; b.classList.add("ghost"); } catch (e) { fail(e); } });
    const r = $("#recRefresh"); if (r) r.onclick = () => recAsk(c);
    renderHomeCoffee();
  } catch (e) { fail(e); }
}
function recAsk(c) {
  openSheet(`<h3>Списались ли вы с этими людьми?</h3><p class="sub">Ответ нужен только нам, чтобы подбор становился точнее.</p>
    <div class="btns"><button class="btn" id="raYes">Да, списались</button><button class="btn ghost" id="raNo">Пока нет</button></div>`, s => {
    s.querySelector("#raNo").onclick = async () => { try { await api("/api/recs/refresh", {json: {met: false}}); closeSheet(); toast("Хорошо, ждем вашего сообщения"); } catch (e) { fail(e); } };
    s.querySelector("#raYes").onclick = async () => { try { const r = await api("/api/recs/refresh", {json: {met: true}}); 
      s.innerHTML = `<h3>Спасибо!</h3><p class="sub">Оставьте короткий отзыв о знакомстве в чате клуба с хештегом <b>${esc(r.tag || "#знакомство")}</b>. Нам важно знать, что получилось.</p>
        <button class="btn" id="raDone">Хорошо</button>`; s.querySelector("#raDone").onclick = () => { closeSheet(); loadCoffee(); }; } catch (e) { fail(e); } };
  });
}
function renderHomeCoffee() {
  const c = S.coffee, el = $("#homeCoffee"); try { renderWeekAction(); } catch (e) {}
  if (!el) return;
  el.hidden = true; return;
  const it = (c && c.items) || [];
  el.innerHTML = it.length ? `<div class="avrow">${it.map(avaEl).join("")}</div><div class="t"><span class="eyebrow">Знакомства месяца</span><b>${esc(it.map(p => p.first_name || fullName(p)).slice(0, 3).join(", "))}</b></div><i>&#8250;</i>`
    : `<div class="t"><span class="eyebrow">Знакомства месяца</span><b>Заполните анкету, и мы подберем людей</b></div><i>&#8250;</i>`;
}

/* ---------- вкладка «Бонусы» ---------- */
async function loadPerks() { renderPerks(); try { const d = await api("/api/offers"); S.offers = d.items; S.slots = d.slots; S.offerDays = d.days; } catch (e) {} renderPerks(); }
const OK_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.500 4.500L19 7.500"/></svg>';
const NO_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';
function renderPerks() {
  const el = $("#perksBox"); if (!el || !S.me) return;
  const yr = !!S.year, amb = S.me.level === "inside", sl = S.slots || {}, g = S.events && S.events.guest, n = S.norm;
  const row = (open, h, p, btn, id) => `<div class="pr ${open ? "" : "lk"}"><div class="t"><b>${h}</b><span>${p}</span></div>${open && btn ? `<button class="btn sm" id="${id}">${btn}</button>` : ""}</div>`;
  const card = (open, name, sub, rows, foot, desc) => `<div class="pcard ${open ? "open" : "closed"}"><div class="ph"><div><h3>${name}</h3><span class="sub">${sub}</span></div><span class="pst ${open ? "ok" : "no"}" aria-label="${open ? "Открыто" : "Закрыто"}">${open ? OK_SVG : NO_SVG}</span></div>${desc ? `<p class="pdesc">${desc}</p>` : ""}${rows}${foot || ""}</div>`;
  const nextEv = ((S.events && S.events.soon) || []).find(e => !e.locked);
  const guestLeft = g ? g.left : 0;
  const yearRows = row(yr, "Ментор клуба и своя рубрика", "Договоритесь с командой о формате", yr ? "Написать" : "", "pkMentor")
    + row(yr, "Место на витрине на год", yr ? (sl.year_free ? "Ваше место свободно: разместите предложение" : "Ваше место занято, предложение на витрине") : "Одно предложение на витрине весь год", sl.year_free ? "Разместить" : "", "pkYearOffer")
    + row(yr, "Гостевые пропуска на эфиры", yr ? `Осталось ${guestLeft} из ${g ? g.total : 2}: друг приходит бесплатно` : "2 в год: друг приходит на эфир бесплатно", guestLeft > 0 && nextEv ? "Позвать друга" : "", "pkGuest")
    + `<p class="psec">Для Амбассадоров на годовом</p>`
    + row(yr && amb, "Выступление на сцене «Единения»", yr && amb ? "Договоритесь с командой о теме и дате" : "Открывается при годовом тарифе и статусе Амбассадора", yr && amb ? "Написать" : "", "pkScene");
  const ambRows = row(amb, "Свой эфир внутри клуба", "Проведите эфир и опубликуйте его для участников", "Предложить", "pkStream")
    + row(amb, "Место на витрине на 1 месяц", amb ? (sl.amb_free ? "Ваше место свободно: разместите предложение на месяц" : "Ваше место занято, предложение на витрине") : "Одно предложение на витрине на 1 месяц", amb && sl.amb_free ? "Разместить" : "", "pkAmbOffer")
    + row(amb, "4 рекомендации знакомств", amb ? "Уже действует: 4 людей в месяц вместо 2" : "Вместо 2 в месяц", "", "")
    + row(amb, "Персональные знакомства", "Подбор людей под ваш запрос", "", "");
  const yearFoot = yr ? "" : `<button class="btn sm ghost" id="pkTeam">Написать команде</button>`;
  const ambFoot = amb ? (n ? `<p class="why ok">${n.done ? `Статус действует еще ${n.days_left} дн.` : "Статус подтверждается шагами"}</p>` : "") : `<p class="why">Открывается за вклад в клуб: ${n ? [n.invite, n.story, n.insight].filter(Boolean).length : 0} из 3 шагов</p><button class="link" id="pkAmbInfo">Как открыть</button>`;
  const full = `<h3>Мои возможности</h3>` + card(amb, "Амбассадор", amb ? "Открыто для вас" : "Пока закрыто", ambRows, ambFoot, "Статус за активное участие в жизни клуба. Бонусы действуют на любом тарифе: годовом и ежемесячном.")
    + card(yr, "Годовой тариф", yr ? "Открыто для вас" : "Пока закрыто", yearRows, yearFoot, "Тариф на год со своими бонусами, плюс дополнительные для Амбассадоров.");
  const sub = [yr ? "годовой тариф" : "", amb ? "амбассадор" : ""].filter(Boolean).join(", ");
  el.innerHTML = `<button class="panel rowcard slim hot" id="perksOpen"><div class="t"><b>Мои возможности</b><span class="sub">${sub ? "Открыто: " + sub : "Годовой тариф и Амбассадор"}</span></div><i>&#8250;</i></button>`;
  $("#perksOpen").onclick = () => openSheet(full, s => {
    const on = (id, f) => { const b = s.querySelector("#" + id); if (b) b.onclick = () => { closeSheet(); f(); }; };
    on("pkYearOffer", newOfferSheet); on("pkAmbOffer", newOfferSheet);
    on("pkGuest", () => guestSheet(nextEv)); on("pkStream", streamSheet); on("pkMentor", ownStream);
    on("pkScene", ownStream); on("pkTeam", () => openPay(S.support || S.join)); on("pkAmbInfo", levelsSheet);
  });
}

/* ---------- профиль ---------- */
const PV = [["pSphere", "cSphere", 40], ["pProject", "cProject", 90], ["pSeek", "cSeek", 140], ["pGive", "cGive", 140]];
function bindPreview() {
  PV.forEach(x => { const el = $("#" + x[0]); if (el && !el.dataset.pv) { el.dataset.pv = 1; el.addEventListener("input", previewCard); } });
  ["pName", "pCity"].forEach(id => { const el = $("#" + id); if (el && !el.dataset.pv) { el.dataset.pv = 1; el.addEventListener("input", previewCard); } });
}
function previewCard() {
  const v = id => ($("#" + id).value || "").trim();
  PV.forEach(x => { const n = ($("#" + x[0]).value || "").length, c = $("#" + x[1]); if (c) { c.textContent = n + " / " + x[2]; c.classList.toggle("warn", n > x[2] - 15); } });
}
function uploadPhoto(f) {
  if (!f) return;
  const img = new Image(), url = URL.createObjectURL(f);
  img.onload = async () => {
    const side = 640, k = Math.min(1, side / Math.max(img.width, img.height)), c = document.createElement("canvas");
    c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
    try { const r = await api("/api/me/photo", {method: "POST", json: {image: c.toDataURL("image/jpeg", 0.85)}}); S.me.photo = r.photo; toast("Фото сохранено"); fillProfile(); } catch (e) { fail(e); }
  };
  img.onerror = () => toast("Не получилось открыть это фото");
  img.src = url;
}
function fillProfile() {
  const m = S.me;
  $("#lvTag").textContent = (m.level === "inside" ? "Амбассадор" : "Резидент") + ""; $("#lvTag").classList.toggle("in", m.level === "inside");
  $("#meCard").innerHTML = `<div class="person"><div class="ava" style="background:${m.photo ? `url(/botpic/${esc(m.photo)}) center/cover` : avaBg(m.tg_id)}"></div>
    <div class="t"><b>${esc(fullName(m))}</b><span>${m.level === "inside" ? "Амбассадор" : "Резидент"}${m.paid_until ? " · до " + new Date(m.paid_until).toLocaleDateString("ru-RU", {day: "numeric", month: "long"}) : ""}</span></div>
    <label class="btn ghost sm photo-btn">${m.photo ? "Сменить" : "Добавить"}<input type="file" id="photoIn" accept="image/*" hidden></label></div>
    `;
  const pin = $("#photoIn"); if (pin) pin.onchange = () => uploadPhoto(pin.files[0]);
  renderLevels();
  renderWants();
  $("#pName").value = m.first_name || ""; $("#pBirth").value = /^\d{4}-\d{2}-\d{2}$/.test(m.birthday || "") ? m.birthday : ""; $("#pSphere").value = m.sphere || ""; $("#pProject").value = m.project || ""; $("#pCity").value = m.city || "";
  $("#pSeek").value = m.seek || ""; $("#pGive").value = m.give || ""; bindPreview(); previewCard();
  $("#pCoffee").setAttribute("aria-pressed", m.coffee ? "true" : "false"); $("#pOff").setAttribute("aria-pressed", m.offline ? "true" : "false");
}
$("#supportBtn").onclick = () => { haptic(); openPay(S.support || "https://t.me/edinenie_support"); };
$$(".toggle").forEach(t => t.onclick = () => t.setAttribute("aria-pressed", t.getAttribute("aria-pressed") === "true" ? "false" : "true"));
$("#saveProfile").onclick = async () => {
  const data = {first_name: $("#pName").value.trim(), birthday: $("#pBirth").value || "", sphere: $("#pSphere").value.trim(), project: $("#pProject").value.trim(), city: $("#pCity").value.trim(), seek: $("#pSeek").value.trim(), give: $("#pGive").value.trim(),
    coffee: $("#pCoffee").getAttribute("aria-pressed") === "true", offline: $("#pOff").getAttribute("aria-pressed") === "true"};
  try {
    await api("/api/me", {method: "PUT", json: data}); Object.assign(S.me, data);
    if (S.wants) { const w = {focus: S.wants.focus || "", goal: $("#wGoal").value.trim(), seek: data.seek, give: data.give};
      const r = await api("/api/wants", {method: "PUT", json: w}); S.wants = Object.assign({}, w, {updated_at: r.updated_at}); refreshHome(); }
    fillProfile(); toast("Анкета сохранена"); haptic();
  } catch (e) { fail(e); }
};
const SPH = ["Деньги", "Смыслы", "Знакомства", "Возможности", "Практики", "Впечатления", "Тело", "Отношения", "Семья", "Работа", "Творчество", "Отдых"];
async function renderWants() {
  if (!$("#wGoal")) return;
  if (!S.wants) { try { S.wants = await api("/api/wants"); } catch (e) { $("#wMonth").hidden = true; return; } }
  const w = S.wants;
  $("#wGoal").value = w.goal || "";
  $("#wSum").textContent = w.goal ? "· заполнено" : "";
}
function renderLevels() {
  const el = $("#levelsCard"), amb = S.me && S.me.level === "inside"; if (!el) return;
  el.innerHTML = `<span class="eyebrow">Ваш статус</span><h3>${amb ? "Амбассадор" : "Резидент"}</h3>
    <p class="sub">${amb ? "Вы проявляетесь в клубе и приводите друзей. Вам доступны свой эфир, витрина и 4 рекомендации знакомств в месяц." : "Станьте Амбассадором: приводите друзей и делитесь клубом. Тогда можно провести свой эфир, попасть на витрину и получать 4 рекомендации в месяц."}</p>
    <button class="btn ghost" id="toLevels">Возможности клуба</button>`;
  $("#toLevels").onclick = levelsSheet;
}

/* ---------- первая анкета ---------- */
// Одна анкета на все: ответы из нее сервер сам переносит в профиль (сфера, город, «ищу», «могу помочь», Random Coffee).
const OB_INT = ["Бизнес", "Деньги и инвестиции", "Психология", "Духовные практики", "Путешествия", "Здоровье и тело", "Творчество", "Образование", "Семья и дети", "Спорт", "Музыка", "Отношения", "Технологии", "Осознанность"];
const OB_INC = ["до 100 тыс. в месяц", "100–300 тыс.", "300–700 тыс.", "от 700 тыс.", "не хочу говорить"];
const parseTags = t => { try { const a = typeof t === "string" ? JSON.parse(t || "[]") : (t || []); return Array.isArray(a) ? a : []; } catch (e) { return []; } };
// Короткое знакомство: один вопрос на экран. Подробную анкету (около 10 минут) можно пройти потом, по желанию.
function showOnboard() {
  const o = $("#onboard"); o.hidden = false;
  const A = {sphere: S.me.sphere || "", city: S.me.city || "", tags: parseTags(S.me.tags), seek: S.me.seek || "", give: S.me.give || "", income: S.me.income || ""};
  const steps = [
    {t: "Чем вы занимаетесь и где живете", s: "Сфера и город. Это видят другие участники.", h: () => `<label class="f" for="oS">СФЕРА</label><input type="text" id="oS" maxlength="40" placeholder="Например: психолог, маркетинг, архитектура" value="${esc(A.sphere)}"><label class="f" for="oC">ГОРОД</label><input type="text" id="oC" maxlength="40" value="${esc(A.city)}">`,
      ok: () => { A.sphere = $("#oS").value.trim(); A.city = $("#oC").value.trim(); return A.sphere && A.city ? "" : "Заполните сферу и город"; }},
    {t: "Что вам интересно", s: "Выберите до пяти тем. По ним мы подскажем, с кем вам по пути.", h: () => `<div class="chips" id="oI">${OB_INT.map(x => `<button class="chip" data-i="${esc(x)}" aria-pressed="${A.tags.includes(x)}">${esc(x)}</button>`).join("")}</div>`,
      bind: () => $$("#oI .chip").forEach(b => b.onclick = () => { const x = b.dataset.i, on = A.tags.includes(x); if (!on && A.tags.length >= 5) { toast("Достаточно пяти тем"); return; } A.tags = on ? A.tags.filter(y => y !== x) : [...A.tags, x]; b.setAttribute("aria-pressed", String(!on)); }),
      ok: () => A.tags.length ? "" : "Выберите хотя бы одну тему"},
    {t: "Кого вы ищете", s: "С кем хотите познакомиться и что ищете сейчас. Одно предложение.", h: () => `<textarea id="oSeek" rows="3" maxlength="140" placeholder="Например: партнеров для совместных проектов, наставника по продажам">${esc(A.seek)}</textarea>`,
      ok: () => { A.seek = $("#oSeek").value.trim(); return A.seek ? "" : "Напишите хотя бы пару слов"; }},
    {t: "Чем вы можете быть полезны", s: "В чем вы по-настоящему сильны. Одно предложение.", h: () => `<textarea id="oGive" rows="3" maxlength="140" placeholder="Например: помогу с упаковкой экспертного продукта">${esc(A.give)}</textarea>`,
      ok: () => { A.give = $("#oGive").value.trim(); return A.give ? "" : "Напишите хотя бы пару слов"; }},
    {t: "Ваш доход", s: "По желанию. Его видит только команда клуба, чтобы подбирать знакомства. Другим участникам он не показывается.", skip: true, h: () => `<div class="chips" id="oInc">${OB_INC.map(x => `<button class="chip" data-i="${esc(x)}" aria-pressed="${A.income === x}">${esc(x)}</button>`).join("")}</div>`,
      bind: () => $$("#oInc .chip").forEach(b => b.onclick = () => { A.income = b.dataset.i; $$("#oInc .chip").forEach(x => x.setAttribute("aria-pressed", String(x === b))); }), ok: () => ""},
  ];
  let i = 0;
  const draw = () => {
    const st = steps[i];
    o.innerHTML = `<span class="eyebrow">${i === 0 ? "Добро пожаловать" : "Шаг " + (i + 1) + " из " + steps.length}</span><h2>${st.t}</h2><p class="note-soft">${st.s}</p>
      <div class="panel">${st.h()}<p class="prof-state" id="oErr"></p><button class="btn" id="oNext">${i === steps.length - 1 ? "Готово" : "Дальше"}</button>${st.skip ? '<button class="btn ghost" id="oSkip" style="margin-top:8px">Пропустить</button>' : ""}${i ? '<button class="btn ghost" id="oBack" style="margin-top:8px">Назад</button>' : ""}</div>
      <p class="note-soft">Нажимая «Дальше», вы соглашаетесь, что другие участники клуба увидят вашу карточку: имя, сферу, город, интересы и ваши ответы.</p>`;
    if (st.bind) st.bind();
    $("#oNext").onclick = () => { const e = st.ok(); if (e) { $("#oErr").textContent = e; return; } if (i < steps.length - 1) { i++; draw(); } else finish(); };
    const sk = $("#oSkip"); if (sk) sk.onclick = () => { A.income = ""; finish(); };
    const bk = $("#oBack"); if (bk) bk.onclick = () => { st.ok(); i--; draw(); };
  };
  const finish = async () => {
    try { await api("/api/me", {method: "PUT", json: {sphere: A.sphere, city: A.city, tags: A.tags, seek: A.seek, give: A.give, income: A.income, consent: true}});
      Object.assign(S.me, {sphere: A.sphere, city: A.city, tags: JSON.stringify(A.tags), seek: A.seek, give: A.give, income: A.income, profile_done: 1, consent_at: new Date().toISOString()});
      o.innerHTML = `<span class="eyebrow">Готово</span><h2>Ваша карточка собрана</h2><p class="note-soft">Ее видят в «Найди своих». Фото и подробности можно добавить в профиле в любой момент.</p>
        <div class="panel"><button class="btn" id="oIn">Войти в клуб</button><button class="btn ghost" id="oLong" style="margin-top:8px">Заполнить подробную анкету (около 10 минут)</button></div>`;
      $("#oIn").onclick = () => { o.hidden = true; start(); };
      $("#oLong").onclick = () => { location.href = "/static/anketa.html" + location.hash; };
    } catch (e) { fail(e); }
  };
  draw();
}
function showOnboardOld() {
  const o = $("#onboard"); o.hidden = false;
  o.innerHTML = `<span class="eyebrow">Добро пожаловать</span><h2>Расскажите о себе</h2>
    <p>Одна анкета, около 10 минут. По ней мы подбираем рекомендации знакомств, а ваш профиль в клубе заполнится сам. Полностью анкету видит только команда клуба. Остальным участникам показываются имя, сфера, проект, город, «ищу» и «могу помочь».</p>
    <div class="panel"><button class="btn" id="oGo">Заполнить анкету</button></div>`;
  $("#oGo").onclick = () => { location.href = "/static/anketa.html" + location.hash; };
}

/* ---------- главная: действие недели и «Ваш месяц» по трем столпам ---------- */
// Шесть сфер анкеты сгруппированы в три столпа клуба.
const PILLARS = [
  {k: "env", t: "Окружение", sph: ["Знакомства", "Впечатления"], hint: "Рекомендации знакомств", btn: "К людям", tab: "people"},
  {k: "game", t: "Большая игра", sph: ["Возможности", "Деньги"], hint: "Материалы про сцену, события и репутацию", btn: "В библиотеку", tab: "lib"},
  {k: "state", t: "Состояние", sph: ["Смыслы", "Практики"], hint: "Практики и эфиры", btn: "В библиотеку", tab: "lib"}
];
async function loadWants() { try { S.wants = await api("/api/wants"); } catch (e) { S.wants = null; } }
function wantsStale() {
  const w = S.wants; if (!w) return false;
  if (!w.goal) return true;
  if (!w.updated_at) return false;
  const u = new Date(w.updated_at), n = new Date();
  return u.getFullYear() !== n.getFullYear() || u.getMonth() !== n.getMonth();
}
async function loadMeet() { try { S.meet = (await api("/api/meet/pending")).items; } catch (e) { S.meet = []; } renderMeetAsk(); try { renderWeekAction(); } catch (e) {} }
function renderMeetAsk() {
  const el = $("#meetAsk"), it = S.meet || []; if (!el) return;
  if (!it.length) { el.innerHTML = ""; return; }
  const p = it[0];
  el.innerHTML = `<div class="panel focus"><span class="eyebrow">Как прошло знакомство</span><h3>Получилось пообщаться с ${esc(p.name)}?</h3>
    <p class="sub">Вы написали неделю назад. Ответ попадет в итоги месяца.</p>
    <div class="btns"><button class="btn sm solid" data-o="met">Встретились или созвонились</button><button class="btn sm" data-o="chat">Переписались</button></div>
    <button class="link" data-o="no">Пока не вышло</button></div>`;
  $$("#meetAsk [data-o]").forEach(b => b.onclick = async () => { try { const r = await api(`/api/recs/${p.id}/outcome`, {json: {outcome: b.dataset.o}}); S.meet = r.items; toast(b.dataset.o === "no" ? "Записали" : "Отлично, записали в итоги"); haptic(); renderMeetAsk(); try { renderWeekAction(); } catch (e) {} } catch (e) { fail(e); } });
}
function routeSteps() {
  const c = S.coffee, m = S.me, ev = S.events || {soon: [], records: []}, s = [];
  if (S.meet && S.meet.length) s.push({h: `Как прошло знакомство с ${S.meet[0].name}?`, p: "Ответ попадет в итоги месяца", btn: "Ответить", tab: "people"});
  if (c && c.items && c.items.length && !c.items.some(i => i.written)) s.push({h: "Напишите людям из рекомендаций", p: `Мы подобрали знакомства на месяц: ${c.items.length}`, btn: "К людям", tab: "people"});
  const unw = (ev.records || []).find(r => !r.locked && !r.watched);
  if (unw) s.push({h: "Посмотрите эфир", p: unw.title + (unw.speaker ? ", " + unw.speaker : ""), btn: "Смотреть", rec: unw});
  const nextEv = (ev.soon || []).find(e => !e.locked && !e.going);
  if (nextEv) s.push({h: "Запишитесь на ближайший эфир", p: nextEv.title, btn: "Открыть", ev: nextEv});
  if (!m.profile_done || !m.seek || !m.give) s.push({h: "Заполните анкету", p: "Кого вы ищете и чем можете помочь: по этому мы подбираем людей", btn: "Заполнить", tab: "profile"});
  if (!m.photo) s.push({h: "Добавьте фото", p: "Людям легче знакомиться с теми, кого они видят", btn: "Добавить", tab: "profile"});
  if (S.wants && wantsStale()) s.push({h: "Напишите фокус на месяц", p: "Одной-двумя фразами: что главное в этом месяце", btn: "Выбрать", tab: "profile"});
  return s;
}
function runStep(st) { closeSheet(); if (st.tab) go(st.tab); else if (st.ev) eventSheet(st.ev); else if (st.rec) recSheet(st.rec); }
function renderWeekAction() {
  const w = $("#welcome"), el = $("#weekAction"); if (!el || !S.me) return;
  const amb = S.me.level === "inside", n = S.norm, done = n ? [n.invite, n.story, n.insight].filter(Boolean).length : 0;
  if (w) w.innerHTML = `<div class="hero"><h3>Добро пожаловать${S.me.first_name ? ", " + esc(S.me.first_name) : ""}</h3></div>`;
  const steps = routeSteps(), st = steps[0], C = 113.1;
  el.hidden = false;
  el.innerHTML = `<span class="eyebrow">Ваш маршрут</span>
    ${st ? `<h3>${esc(st.h)}</h3><p class="sub">${esc(st.p)}</p><button class="btn solid" id="wkGo">${esc(st.btn)}</button>`
         : `<h3>Все шаги пройдены</h3><p class="sub">Загляните в эфиры и библиотеку: там всегда есть что-то новое.</p><button class="btn solid" data-tab="events">К эфирам</button>`}
    <div class="ringrow" id="wkAmb" role="button" tabindex="0"><svg viewBox="0 0 44 44" width="44" height="44"><circle cx="22" cy="22" r="18" class="rb"/><circle cx="22" cy="22" r="18" class="rf" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-off="${(C * (1 - done / 3)).toFixed(1)}" transform="rotate(-90 22 22)"/><text x="22" y="26" text-anchor="middle">${done}/3</text></svg>
      <div class="t"><b>${amb ? "Вы Амбассадор" : "Путь Амбассадора"}</b><span>${amb ? (n && n.done ? `Статус действует еще ${n.days_left} дн.` : "Повторите три шага, чтобы сохранить статус") : "Свой эфир, витрина, 4 знакомства в месяц"}</span></div><i>&#8250;</i></div>
    ${steps.length > 1 ? `<button class="link" id="wkAll">Весь маршрут: еще ${steps.length - 1}</button>` : ""}`;
  requestAnimationFrame(() => requestAnimationFrame(() => { const f = el.querySelector(".rf"); if (f) f.style.strokeDashoffset = f.dataset.off; }));
  const g = $("#wkGo"); if (g) g.onclick = () => runStep(st);
  const r = $("#wkAmb"); if (r) r.onclick = routeSheet;
  const al = $("#wkAll"); if (al) al.onclick = routeSheet;
}
function routeSheet() {
  const amb = S.me.level === "inside", n = S.norm, steps = routeSteps();
  const li = (ok, h, p) => `<li class="${ok ? "ok" : ""}"><i></i><div><b>${esc(h)}</b><span>${esc(p)}</span></div></li>`;
  const items = [["invite", "Привести друга в клуб", "Он должен оплатить участие"], ["story", "Два раза рассказать о клубе в сторис", `С хештегом #делюсь в чате клуба. Подтверждено: ${n ? n.story_n || 0 : 0} из 2`], ["insight", "Написать инсайт после эфира", "С хештегом #инсайт в чате клуба"]];
  const perks = ["Провести свой эфир внутри клуба и опубликовать его", "Разместиться на витрине предложений", "Получать 4 рекомендации знакомств в месяц вместо 2"];
  openSheet(`<h3>Ваш маршрут</h3>
    ${steps.length ? `<p class="sub"><b>Что можно сделать</b></p><ul class="norm">${steps.map((s, i) => `<li data-i="${i}" style="cursor:pointer"><i></i><div><b>${esc(s.h)}</b><span>${esc(s.p)}</span></div></li>`).join("")}</ul>` : ""}
    <p class="sub" style="margin-top:6px"><b>${amb ? "Чтобы сохранить статус Амбассадора" : "Путь Амбассадора"}</b></p>
    ${n ? `<ul class="norm">${items.map(i => li(n[i[0]], i[1], n[i[0]] ? "Подтверждено командой" : i[2])).join("")}</ul>` : ""}
    <p class="sub"><b>Что дает Амбассадорство</b><br>${perks.map(t => "· " + esc(t)).join("<br>")}</p>
    <div class="btns"><button class="btn" id="wkInv">Пригласить друга</button><button class="btn ghost" id="wkStream">Предложить свой эфир</button></div>
    <button class="btn ghost" id="wkMore">Об уровнях</button>`, s => {
    s.querySelectorAll("li[data-i]").forEach(x => x.onclick = () => runStep(steps[+x.dataset.i]));
    s.querySelector("#wkStream").onclick = () => { closeSheet(); streamSheet(); };
    s.querySelector("#wkMore").onclick = () => { closeSheet(); levelsSheet(); };
    s.querySelector("#wkInv").onclick = () => { const k = (S.rules || []).find(r => r.code === "invite"); closeSheet(); if (k) taskSheet(k); else toast("Ссылка загрузится через секунду, попробуйте еще раз"); };
  });
}
function renderMonth() {
  // когда ритуал выполнен, он скрывается, а на его месте остается фокус месяца: сфера и цель человека его словами
  const el = $("#monthCard"), w = S.wants, d = S.daily; if (!el) return;
  const done = d && (d.mood != null) && d.focus && d.card && d.areas.length > 0 && !S.rfEdit && !S.mEdit && !S.aEdit && !S.rOpen;
  if (!done || !w || !w.goal) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<span class="eyebrow">Фокус на месяц</span>
    <p class="mgoal">${esc(w.goal)}</p>
    <div class="moods mini">${MOODS.map((m, i) => `<button data-mood="${i + 1}" aria-pressed="${d.mood === i + 1}" aria-label="${m[0]}" style="--c:${m[1]}"><span></span></button>`).join("")}</div>
    <div class="mfoot"><span class="mdone"><i class="mck"></i>Ритуал выполнен · ${d.streak} дн.</span><span class="mlinks"><button class="link" id="mcOpen">Ритуал</button><button class="link" id="mcEdit">Фокус</button></span></div>`;
  $("#mcEdit").onclick = () => { S.rfEdit = true; renderRitual(); };
  $("#mcOpen").onclick = () => { S.rOpen = true; renderRitual(); };
  $$("#monthCard [data-mood]").forEach(b => b.onclick = () => dailyStep("mood", {value: +b.dataset.mood}));
}
function refreshHome() { renderWeekAction(); renderMonth(); renderRitual(); }

/* ---------- заявка на свой эфир ---------- */
function ownStream() {
  const E = S.events || {}, contact = E.stream_contact;
  if (S.year) {
    openSheet(`<h3>Провести эфир в клубе</h3><p class="sub">На годовом тарифе вы можете стать ментором клуба и вести свою рубрику, а также проводить свои эфиры. Напишите нам, договоримся о формате и дате.</p><button class="btn" id="osGo">Написать</button>`,
      s => s.querySelector("#osGo").onclick = () => { closeSheet(); if (contact) openTg(contact); else toast("Контакт пока не указан"); });
  } else if (S.me && S.me.level === "inside") { streamSheet(); }
  else {
    openSheet(`<h3>Провести эфир в клубе</h3><p class="sub">Стать ментором клуба и вести свою рубрику можно на годовом тарифе.</p><button class="btn" id="osBuy">Перейти на годовой тариф</button>`,
      s => s.querySelector("#osBuy").onclick = () => { closeSheet(); openPay(E.buy_url); });
  }
}
function streamSheet() {
  if (!S.me || S.me.level !== "inside") { openSheet(`<h3>Свой эфир</h3><p class="sub">Провести свой эфир внутри клуба могут Амбассадоры. Статус открывается за вклад: друг, два рассказа о клубе в сторис, инсайт после эфира.</p><button class="btn" id="stHow">Как стать Амбассадором</button>`, s => s.querySelector("#stHow").onclick = () => { closeSheet(); levelsSheet(); }); return; }
  openSheet(`<h3>Предложить свой эфир</h3><p class="sub">Расскажите, о чем хотите провести эфир. Команда свяжется с вами и договорится о формате.</p>
    <label class="f" for="stT">ТЕМА<input type="text" id="stT" maxlength="120" placeholder="О чем эфир"></label>
    <label class="f" for="stB">О ЧЕМ РАССКАЖЕТЕ<textarea id="stB" rows="4" maxlength="800" placeholder="Две-три фразы: тема, для кого, что получат участники"></textarea></label>
    <label class="f" for="stW">КОГДА УДОБНО<input type="text" id="stW" maxlength="120" placeholder="Например: декабрь, вечер будней"></label>
    <button class="btn" id="stGo">Отправить заявку</button>`, s => {
    s.querySelector("#stGo").onclick = async () => {
      const t = s.querySelector("#stT").value.trim(), b = s.querySelector("#stB").value.trim();
      if (!t || !b) { toast("Напишите тему и о чем будет эфир"); return; }
      const btn = s.querySelector("#stGo"); btn.disabled = true;
      try { await api("/api/stream-request", {json: {title: t, body: b, when: s.querySelector("#stW").value}}); closeSheet(); toast("Заявка отправлена команде"); }
      catch (e) { btn.disabled = false; fail(e); } };
  });
}

/* версия приложения внизу профиля: видно, дошло ли обновление */
fetch("/api/version", {cache: "no-store"}).then(r => r.json()).then(j => { const el = $("#verStamp"); if (el && j.v) el.textContent = "Версия от " + new Date(j.v * 1000).toLocaleString("ru-RU", {day: "numeric", month: "long", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow"}); }).catch(() => {});

/* ---------- итоги месяца: кнопка с 28 числа, пока не заполнены ---------- */
const MON_G = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"], MON_N = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
/* ---------- самообновление ---------- */
// Мини-приложение в Telegram может неделями жить в фоне. Когда его открывают снова, сверяем версию и перезагружаем, если вышла новая.
(function () {
  const sc = document.querySelector('script[src*="/static/app.js"]'), m = sc && /[?&]v=(\d+)/.exec(sc.src);
  if (!m) return;
  const mine = m[1];
  async function check() {
    try { const r = await fetch("/api/version", {cache: "no-store"}); const d = await r.json();
      if (d.v && String(d.v) !== mine && !document.getElementById("quoteFs")) location.reload(); } catch (e) {}
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
  window.addEventListener("focus", check);
  setInterval(check, 5 * 60 * 1000);
})();

/* ---------- послание дня ---------- */
async function openQuote() {
  try {
    const q = await api("/api/quote"); track("quote");
    if (!(S.daily && S.daily.card)) dailyStep("card");
    const ov = document.createElement("div"); ov.id = "quoteFs";
    ov.innerHTML = `<img src="${esc(q.url)}" alt="${esc(q.text)}"><button class="qsave" aria-label="Сохранить в галерею"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7.5 11 12 15.5 16.5 11M5 19h14"/></svg></button><button class="qx" aria-label="Закрыть">&#10005;</button>`;
    document.body.appendChild(ov);
    const close = () => { ov.classList.remove("on"); setTimeout(() => ov.remove(), 250); };
    requestAnimationFrame(() => ov.classList.add("on"));
    ov.querySelector(".qx").onclick = close;
    ov.querySelector(".qsave").onclick = async () => {
      // 1) системное меню «Поделиться» с файлом: там есть «Сохранить изображение» в галерею; 2) если его нет, бот присылает фото в чат
      try {
        const blob = await (await fetch(q.url)).blob(), file = new File([blob], `edinenie-${q.date}.jpg`, {type: "image/jpeg"});
        if (navigator.canShare && navigator.canShare({files: [file]})) { await navigator.share({files: [file]}); return; }
      } catch (e) { if (e && e.name === "AbortError") return; }
      try { await api("/api/quote/send", {method: "POST", json: {}}); toast("Прислали картинку в чат с ботом: нажмите на нее и выберите «Сохранить в галерею»"); }
      catch (e) { fail(e); }
    };
  } catch (e) { fail(e); }
}
const _hp = $("#homePerks"); if (_hp) _hp.onclick = levelsSheet;
/* ---------- профиль: трекинг прогресса ---------- */
function progChart(P) {
  const W = 340, H = 170, L = 8, R = 8, T = 10, B = 24, n = P.series.length, X = i => L + (n === 1 ? 0 : i * (W - L - R) / (n - 1)), Y = v => T + (5 - v) * (H - T - B) / 4;
  const pts = P.series.map((x, i) => x.mood ? [X(i), Y(x.mood), x] : null).filter(Boolean);
  const grid = [1, 2, 3, 4, 5].map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" stroke-width="1" ${v % 2 ? 'stroke-dasharray="3 5"' : ""}/>`).join("");
  const line = pts.length > 1 ? `<path d="${pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ")}" fill="none" stroke="var(--accent)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>` : "";
  const dots = pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${n > 40 ? 2 : 4}" fill="${MOODS[p[2].mood - 1][1]}" stroke="var(--bg, #0f1120)" stroke-width="1.5"/>`).join("");
  const bw = Math.max(2, (W - L - R) / n - 2), bars = P.series.map((x, i) => `<rect x="${(X(i) - bw / 2).toFixed(1)}" y="${H - B + 6 + (3 - x.n) * 3}" width="${bw.toFixed(1)}" height="${Math.max(1, x.n * 3)}" rx="1" fill="${x.n >= 2 ? "var(--accent)" : "var(--line-strong)"}" opacity="${x.n ? 1 : .35}"/>`).join("");
  const lab = [0, Math.floor((n - 1) / 2), n - 1].map(i => { const d = P.series[i].d.split("-"); return `<text x="${X(i)}" y="${H + 8}" text-anchor="${i === 0 ? "start" : i === n - 1 ? "end" : "middle"}" fill="var(--muted)" font-size="10">${+d[2]} ${MON_G[+d[1] - 1].slice(0, 3)}</text>`; }).join("");
  const yl = [[5, "на подъеме"], [1, "тяжело"]].map(([v, t]) => `<text x="${L + 2}" y="${Y(v) + (v === 5 ? 12 : -4)}" fill="var(--muted)" font-size="9" opacity=".8">${t}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H + 12}" width="100%" role="img" aria-label="График состояния по дням">${grid}${yl}${line}${dots}${bars}${lab}</svg>`;
}
function progAreas(P) {
  const A = P.areas || [], used = A.filter(x => x.days);
  if (!used.length) return `<div class="pg-areas"><h4>Что влияет на состояние</h4><p class="sub">Отмечайте на главной, чему уделяете внимание: тело, отношения, отдых, веселье, деньги. Через пару недель здесь будет видно, какие сферы поднимают ваше состояние.</p></div>`;
  const top = A.filter(x => x.effect != null && x.effect >= 0.3).sort((a, b) => b.effect - a.effect)[0], max = Math.max(...used.map(x => x.days), 1);
  return `<div class="pg-areas"><h4>Что влияет на состояние</h4>
    ${top ? `<p class="pg-ins">В дни, когда вы уделяете внимание сфере «${AREAS[top.k]}», состояние в среднем выше на ${top.effect}.</p>` : '<p class="sub">Пока мало данных для выводов: нужно хотя бы по 3 дня с отметкой и без нее.</p>'}
    ${used.sort((x, y) => y.days - x.days).map(x => `<div class="ar"><span class="an">${AREAS[x.k]}</span><span class="ab"><i style="width:${Math.round(x.days / max * 100)}%"></i></span><span class="ad">${x.days} дн.</span><span class="ae ${x.effect == null ? "" : x.effect > 0 ? "up" : x.effect < 0 ? "dn" : ""}">${x.effect == null ? "—" : (x.effect > 0 ? "+" : "") + x.effect}</span></div>`).join("")}
    <p class="sub" style="margin-top:8px">Справа разница среднего состояния в дни с этой сферой и без нее. Это наблюдение за вашими днями, а не доказанная причина.</p></div>`;
}
async function progressSheet(days) {
  days = days || 30;
  let P; try { P = await api("/api/progress?days=" + days); } catch (e) { fail(e); return; }
  const delta = P.avg != null && P.prev != null ? Math.round((P.avg - P.prev) * 10) / 10 : null;
  const few = P.series.filter(x => x.mood).length < 3;
  openSheet(`<h3>Мой прогресс</h3>
    <div class="chips" id="pgR">${[7, 30, 90].map(d => `<button class="chip" data-d="${d}" aria-pressed="${d === P.days}">${d} дней</button>`).join("")}</div>
    <div class="pg-chart">${progChart(P)}<div class="pg-leg"><span><i style="background:var(--accent)"></i>состояние</span><span class="b"><i></i>шаги ритуала (внизу)</span></div></div>
    ${few ? '<p class="sub">Пока мало данных. Отмечайте состояние на главной каждый день, и через неделю здесь появится ваша линия.</p>' : ""}
    <div class="pg-stats">
      <div><b>${P.streak}</b><span>серия сейчас</span></div><div><b>${P.best}</b><span>лучшая серия</span></div>
      <div><b>${P.done}<small> из ${P.days}</small></b><span>дней с ритуалом</span></div>
      <div><b>${P.avg != null ? P.avg : "—"}${delta != null && delta !== 0 ? `<small class="${delta > 0 ? "up" : "dn"}"> ${delta > 0 ? "+" : ""}${delta}</small>` : ""}</b><span>среднее состояние${delta != null ? " (к прошлому периоду)" : ""}</span></div></div>
    ${progAreas(P)}
    <div class="switch"><span>Напоминание в 10:00 по Москве</span><button class="toggle" id="pgPush" aria-pressed="${P.push}" aria-label="Напоминание в 10:00"></button></div>`, s => {
    s.querySelectorAll("#pgR .chip").forEach(b => b.onclick = () => progressSheet(+b.dataset.d));
    const t = s.querySelector("#pgPush"); t.onclick = async () => { const on = t.getAttribute("aria-pressed") !== "true"; try { await api("/api/daily/push", {json: {on}}); t.setAttribute("aria-pressed", String(on)); toast(on ? "Напоминание включено" : "Напоминание выключено"); } catch (e) { fail(e); } };
  });
}
const _pb = $("#progBtn"); if (_pb) _pb.onclick = () => progressSheet(30);

/* ---------- ритуал дня на главной: состояние, фокус, карта ---------- */
const AREAS = {body: "Тело", sleep: "Сон", relations: "Отношения", family: "Семья", friends: "Друзья", rest: "Отдых", fun: "Веселье", money: "Деньги", work: "Работа", learn: "Учеба", create: "Творчество", nature: "Природа"};
const MOODS = [["Тяжело", "#6C7AA8"], ["Устало", "#8E86B8"], ["Ровно", "#B99BC0"], ["Хорошо", "#E0A27E"], ["На подъеме", "#F2C27A"]];
async function loadDaily() { try { S.daily = await api("/api/daily"); } catch (e) { S.daily = null; } renderRitual(); const ps = $("#progSub"); if (ps && S.daily) ps.textContent = S.daily.streak ? `Серия: ${S.daily.streak} дн.` : ""; }
async function dailyStep(step, extra) { try { S.daily = await api("/api/daily", {method: "POST", json: Object.assign({step}, extra || {})}); renderRitual(); haptic(); } catch (e) { fail(e); } }
function renderRitual() {
  const el = $("#ritual"), d = S.daily; if (!el) return;
  if (!d) { el.hidden = true; return; }
  el.hidden = false; renderMonth();
  const w = S.wants || {}, fp = w.goal, n = (d.mood != null) + d.focus + d.card + (d.areas.length > 0), edit = !!S.rfEdit;
  const done = n >= 4;
  if (done && !edit && !S.mEdit && !S.aEdit && !S.rOpen && w.goal) { el.hidden = true; return; }
  const wk = d.week.map(x => `<i class="${x.n >= 2 ? "on" : ""}" ${x.mood ? `style="background:${MOODS[x.mood - 1][1]}"` : ""}></i>`).join("");
  const row = (ok, t, sub, btn) => `<div class="rstep rrow ${ok ? "ok" : ""}"><div class="rt"><i class="ck"></i><div class="rtx"><b>${t}</b>${sub ? `<span>${sub}</span>` : ""}</div>${btn || ""}</div></div>`;
  const mood = d.mood != null && !S.mEdit ? row(1, "Состояние: " + MOODS[d.mood - 1][0].toLowerCase(), "", '<button class="btn sm ghost" id="rmEdit">Изменить</button>')
    : `<div class="rstep"><div class="rt"><i class="ck"></i><b>Как вы сейчас?</b></div>
      <div class="moods">${MOODS.map((m, i) => `<button data-mood="${i + 1}" aria-pressed="${d.mood === i + 1}" style="--c:${m[1]}"><span></span>${m[0]}</button>`).join("")}</div></div>`;
  const areas = d.areas.length && !S.aEdit ? row(1, "Внимание: " + d.areas.map(k => AREAS[k].toLowerCase()).join(", "), "", '<button class="btn sm ghost" id="raEdit">Изменить</button>')
    : `<div class="rstep"><div class="rt"><i class="ck"></i><b>Чему уделите внимание сегодня?</b></div>
      <div class="chips" id="rAreas">${Object.keys(AREAS).map(k => `<button class="chip" data-a="${k}" aria-pressed="${d.areas.includes(k)}">${AREAS[k]}</button>`).join("")}</div>
      ${d.areas.length ? '<div class="btns"><button class="btn sm solid" id="raDone">Готово</button></div>' : ''}</div>`;
  const focus = edit || !fp ? `<div class="rstep"><div class="rt"><i class="ck"></i><b>Ваш фокус на месяц</b></div><textarea id="rfGoal" rows="2" placeholder="Например: запустить продажи и каждый день гулять">${esc(w.goal || "")}</textarea>
        <div class="btns"><button class="btn sm solid" id="rfSave">Сохранить</button>${fp ? '<button class="btn sm ghost" id="rfCancel">Отмена</button>' : ""}</div></div>`
    : row(d.focus, "Фокус на месяц", esc(w.goal), `<span class="rbt">${d.focus ? "" : '<button class="btn sm" id="rFocus">Помню</button>'}<button class="btn sm ghost" id="rfEdit">Изменить</button></span>`);
  const card = row(d.card, "Карта дня", "", `<button class="btn sm ${d.card ? "ghost" : ""}" id="rCard">${d.card ? "Открыть" : "Вытянуть"}</button>`);
  el.innerHTML = `<div class="rhead"><h3>${done ? "Ритуал дня выполнен" : "Ритуал на сегодня"}</h3>${done && S.rOpen ? '<button class="btn sm ghost" id="rClose">Свернуть</button>' : ""}<div class="rstreak"><b>${d.streak}</b><span>${d.streak === 1 ? "день" : d.streak >= 2 && d.streak <= 4 ? "дня" : "дней"} подряд</span></div></div>
    <div class="rweek">${wk}</div>${mood}${areas}${focus}${card}`;
  const rcl = $("#rClose"); if (rcl) rcl.onclick = () => { S.rOpen = false; S.mEdit = S.aEdit = S.rfEdit = false; renderRitual(); };
  const em = $("#rmEdit"); if (em) em.onclick = () => { S.mEdit = true; renderRitual(); };
  const ea = $("#raEdit"); if (ea) ea.onclick = () => { S.aEdit = true; renderRitual(); };
  const ad = $("#raDone"); if (ad) ad.onclick = () => { S.aEdit = false; renderRitual(); };
  $$("#ritual #rAreas .chip").forEach(b => b.onclick = () => { const cur = new Set(S.daily.areas), k = b.dataset.a; cur.has(k) ? cur.delete(k) : cur.add(k); dailyStep("areas", {value: [...cur]}); });
  $$("#ritual [data-mood]").forEach(b => b.onclick = () => { S.mEdit = false; dailyStep("mood", {value: +b.dataset.mood}); });
  const f = $("#rFocus"); if (f) f.onclick = () => dailyStep("focus", {on: true});
  const re = $("#rfEdit"); if (re) re.onclick = () => { S.rfEdit = true; renderRitual(); };
  const rc = $("#rfCancel"); if (rc) rc.onclick = () => { S.rfEdit = false; renderRitual(); };
  const rs = $("#rfSave"); if (rs) rs.onclick = async () => {
    const data = {focus: (S.wants && S.wants.focus) || "", goal: $("#rfGoal").value.trim(), seek: (S.wants && S.wants.seek) || S.me.seek || "", give: (S.wants && S.wants.give) || S.me.give || ""};
    if (!data.goal) { toast("Напишите фокус"); return; }
    try { const r = await api("/api/wants", {method: "PUT", json: data}); S.wants = Object.assign({}, S.wants, data, {updated_at: r.updated_at}); S.rfEdit = false; try { renderWants(); } catch (e) {} await dailyStep("focus", {on: true}); refreshHome(); toast("Фокус сохранен"); }
    catch (e) { fail(e); } };
  const c = $("#rCard"); if (c) c.onclick = openQuote;
}

$("#anketaToggle").onclick = () => { const b = $("#anketaBody"), o = b.hidden; b.hidden = !o; $("#anketaToggle").setAttribute("aria-expanded", String(o)); };
/* ---------- аватарка из Telegram ---------- */
async function tgAvatar() {
  // Нет фото: сначала пробуем забрать аватарку из Telegram прямо в приложении (это работает и когда сервер не достает до Telegram),
  // не вышло, просим сервер.
  try {
    const u = TG && TG.initDataUnsafe && TG.initDataUnsafe.user, m = S.me;
    if (!m || m.photo || sessionStorage.getItem("ava")) return;
    sessionStorage.setItem("ava", "1");
    const url = (u && u.photo_url) || "";
    const save = async blob => {
      const bmp = await new Promise((ok, no) => { const im = new Image(), o = URL.createObjectURL(blob); im.onload = () => ok(im); im.onerror = no; im.src = o; });
      const side = 640, k = Math.min(1, side / Math.max(bmp.width, bmp.height)), c = document.createElement("canvas");
      c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      const r = await api("/api/me/photo", {method: "POST", json: {image: c.toDataURL("image/jpeg", 0.85)}});
      S.me.photo = r.photo; fillProfile(); refreshHome(); return true;
    };
    if (url) {
      try { if (await save(await (await fetch(url, {mode: "cors"})).blob())) return; } catch (e) {}
      try {
        const done = await new Promise(ok => { const img = new Image(); img.crossOrigin = "anonymous";
          img.onload = async () => { try { const c = document.createElement("canvas"); c.width = img.width; c.height = img.height; c.getContext("2d").drawImage(img, 0, 0);
            c.toBlob(async b => { try { ok(b ? await save(b) : false); } catch (e) { ok(false); } }, "image/jpeg", 0.9); } catch (e) { ok(false); } };
          img.onerror = () => ok(false); img.src = url; });
        if (done) return;
      } catch (e) {}
    }
    const r = await api("/api/me/photo-tg", {json: {url}});
    if (r && r.photo) { S.me.photo = r.photo; fillProfile(); refreshHome(); }
  } catch (e) {}
}

/* ---------- запуск ---------- */
async function start() {
  $("#main").hidden = false; $("#tabs").hidden = false; $("#ptsPill").hidden = false;
  fillProfile();
  await Promise.allSettled([refreshPoints().then(fillProfile), loadEvents(), loadCal(), loadHomeLib(), loadFeed(), loadCoffee(), loadWants(), loadDaily(), loadMeet()]);
  refreshHome(); tgAvatar();
  route();
}
async function boot() {
  if (TG) { TG.ready(); TG.expand(); try { TG.setHeaderColor("#0A0D1A"); TG.setBackgroundColor("#0A0D1A"); } catch (e) {} }
  try {
    const d = await api("/api/me"); S.me = d.me; S.year = !!d.year; S.join = d.join; S.support = d.support; S.stats = d.stats; S.points = d.points; S.norm = d.norm || null; $("#gateJoin").href = d.join;
    $("#boot").hidden = true;
    if (d.me.status !== "active") {
      $("#gate").hidden = false;
      if (d.me.status === "expired") { $("#gateTitle").textContent = "Участие закончилось"; $("#gateText").textContent = "Продлите участие, и все ваши знакомства и материалы вернутся."; $("#gateJoin").textContent = "Продлить участие"; }
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
