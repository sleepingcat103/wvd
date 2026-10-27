const api = () => window.pywebview.api;
const pages = [
  ["target", "任務目標", "i-target"],
  ["explore", "探索設定", "i-map"],
  ["combat", "戰鬥配置", "i-bolt"],
  ["strategies", "戰鬥方案", "i-sliders"],
  ["system", "模擬器", "i-cpu"],
  ["advanced", "進階設定", "i-shield"],
  ["timer", "計時器", "i-clock"],
  ["about", "關於", "i-info"]
];
const labels = {
  QUICK_DISARM_CHEST: "快速開箱", DO_COMBAT_RECOVER: "戰鬥結束後恢復", DO_CHEST_RECOVER: "開箱後恢復",
  RECOVER_WHEN_BEGINNING: "進入地下城時恢復", RECOVER_AFTER_REST: "住宿後首次進本恢復", ACTIVE_REST: "啟用旅店休息",
  RE_ASSEMBLE_PARTY: "定時重置隊伍並整理背包", ACTIVE_DIGGING: "無再起之火時嘗試挖礦", ACTIVE_BEG_MONEY: "無再起之火時嘗試刷錢",
  ACTIVE_FISHING: "無再起之火時嘗試釣魚", ACTIVE_ROYALSUITE_REST: "入住豪華房", ACTIVE_TRIUMPH: "跳躍至第三章結局「凱旋」",
  ACTIVE_BEAUTIFUL_ORE: "跳躍至第四章結局「美麗礦石的真相」", ACTIVE_CSC: "嘗試調整因果", BYPASS_THE_WALL: "重啟後嘗試繞過空氣牆"
};
let state = null, updateData = null, activePage = "target", dirty = false, checkingUpdate = true, updateCheckError = false, manualUpdateCheck = false, initializing = true, compactMode = localStorage.getItem("wvd-ui-mode") === "compact";
const promptedUpdates = new Set();

const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const icon = id => `<svg aria-hidden="true"><use href="#${id}"/></svg>`;
const field = (name, label, type="text", help="") => `<div class="field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${esc(state.config[name])}">${help ? `<small>${help}</small>` : ""}</div>`;
const select = (name, label, options, help="") => `<div class="field"><label for="${name}">${label}</label><select id="${name}" name="${name}">${options.map(([v,l]) => `<option value="${esc(v)}" ${String(state.config[name])===String(v)?"selected":""}>${esc(l)}</option>`).join("")}</select>${help ? `<small>${help}</small>` : ""}</div>`;
const checks = names => `<div class="check-list">${names.map(n => `<label class="check-row"><input type="checkbox" name="${n}" ${state.config[n]?"checked":""}><span>${labels[n]}</span></label>`).join("")}</div>`;
const card = (title, desc, body, cls="") => `<section class="card ${cls}"><div class="card-head"><div><h2>${title}</h2>${desc?`<p>${desc}</p>`:""}</div></div>${body}</section>`;

let modalResolve = null, modalDetailed = false;
function closeModal(result) {
  const dialog = $("#app-modal");
  if (!dialog.open) return;
  const details = {confirmed: result, checked: $("#modal-option").checked};
  dialog.close();
  const resolve = modalResolve;
  modalResolve = null;
  resolve?.(modalDetailed ? details : result);
}
function openModal({title="提示", message="", confirmText="確定", cancelText="", checkboxLabel="", wide=false, details=false}) {
  if ($("#app-modal").open) closeModal(false);
  $("#modal-title").textContent = title;
  $("#modal-message").textContent = String(message ?? "");
  $("#modal-confirm").textContent = confirmText;
  $("#modal-cancel").textContent = cancelText;
  $("#modal-cancel").hidden = !cancelText;
  $("#modal-option-label").textContent = checkboxLabel;
  $("#modal-option-row").hidden = !checkboxLabel;
  $("#modal-option").checked = false;
  $("#app-modal").classList.toggle("wide", wide);
  modalDetailed = details;
  return new Promise(resolve => {
    modalResolve = resolve;
    $("#app-modal").showModal();
    $("#modal-confirm").focus();
  });
}
const appAlert = (message, title="提示", options={}) => openModal({title, message, ...options});
const appConfirm = (message, title="確認") => openModal({title, message, cancelText:"取消"});
window.alert = appAlert;
window.confirm = appConfirm;
async function showChangelog() {
  await appAlert(await api().get_changelog(), "更新日誌", {confirmText:"我了解了", wide:true});
  if (state && state.config.LAST_VERSION !== state.version) {
    await api().acknowledge_changelog();
    state.config.LAST_VERSION = state.version;
  }
}
function updateHtml() {
  const latest = updateData?.version || state.config.LATEST_VERSION || "—";
  const ignored = updateData && state.config.IGNORED_UPDATE_VERSION === updateData.version;
  const status = checkingUpdate ? "檢查中" : updateCheckError ? "檢查失敗" : updateData ? ignored ? "已忽略" : "可更新" : "已是最新版";
  return `<section class="about-update"><div class="update-heading"><div><strong>版本更新</strong><small>目前版本 v${esc(state.version)}</small></div><span class="update-status ${updateCheckError?"error":updateData&&!ignored?"available":""}">${status}</span></div><label class="check-row"><input type="checkbox" id="auto-update" ${state.config.AUTO_UPDATE?"checked":""}><span><strong>自動更新</strong><small>啟用後顯示確認更新視窗，不會未經確認下載</small></span></label><div class="update-release"><div><small>最新版本</small><strong>${latest==="—"?latest:`v${esc(latest)}`}</strong></div><div class="toolbar"><button class="ghost-button" id="check-update" ${checkingUpdate?"disabled":""}>${checkingUpdate?"檢查中…":"檢查更新"}</button>${updateData?`<button class="secondary-button" id="install-update">更新至 v${esc(updateData.version)}</button>`:""}</div></div><div class="progress" hidden><i></i></div></section>`;
}
function renderUpdatePanel() {
  const panel = $("#update-settings");
  if (!panel) return;
  panel.innerHTML = updateHtml();
  wireUpdateControls();
}
async function ignoreUpdate(version) {
  const result = await api().ignore_update(version);
  if (result.ok) state.config.IGNORED_UPDATE_VERSION = version;
}
async function promptUpdate(data) {
  const choice = await openModal({
    title: "確認自動更新",
    message: `發現 WvDAS v${data.version}。是否立即下載並安裝？`,
    confirmText: "立即更新",
    cancelText: "稍後",
    checkboxLabel: `忽略 v${data.version}，不再提醒`,
    details: true
  });
  if (choice.checked) {
    await ignoreUpdate(data.version);
    renderUpdatePanel();
    return;
  }
  if (choice.confirmed) beginUpdate();
}
async function confirmUpdate() {
  if (!updateData) return;
  const choice = await openModal({title:"確認更新",message:`即將下載並安裝 WvDAS v${updateData.version}，完成後應用程式會重新啟動。`,confirmText:"開始更新",cancelText:"取消",checkboxLabel:`忽略 v${updateData.version}，不再提醒`,details:true});
  if (choice.checked) { await ignoreUpdate(updateData.version); renderUpdatePanel(); return; }
  if (choice.confirmed) beginUpdate();
}
function beginUpdate() {
  const button = $("#install-update");
  if (button) { button.disabled = true; button.textContent = "準備下載…"; }
  api().download_update();
}
function notifyUpdate(data) {
  if (initializing || !state.config.AUTO_UPDATE || state.config.IGNORED_UPDATE_VERSION === data.version || promptedUpdates.has(data.version)) return;
  promptedUpdates.add(data.version);
  promptUpdate(data);
}
function wireUpdateControls() {
  const automatic = $("#auto-update");
  if (automatic) automatic.onchange = async () => { const enabled=automatic.checked, result=await api().set_auto_update(enabled); if(result.ok){state.config.AUTO_UPDATE=enabled;if(enabled&&updateData)notifyUpdate(updateData);}else{automatic.checked=!enabled;toast({message:"無法儲存自動更新設定",type:"error"});} };
  const check = $("#check-update");
  if (check) check.onclick = async () => { checkingUpdate=true;updateCheckError=false;manualUpdateCheck=true;renderUpdatePanel();const result=await api().check_for_updates();if(!result.ok){checkingUpdate=false;manualUpdateCheck=false;renderUpdatePanel();toast({message:result.error,type:"error"});} };
  const install = $("#install-update");
  if (install) install.onclick = confirmUpdate;
}

$("#modal-confirm").onclick = () => closeModal(true);
$("#modal-cancel").onclick = () => closeModal(false);
$("#modal-close").onclick = () => closeModal(false);
$("#app-modal").addEventListener("cancel", event => { event.preventDefault(); closeModal(false); });

function renderNav() {
  $("#nav").innerHTML = pages.map(([id,label,ic]) => `<button class="nav-button ${id===activePage?"active":""}" data-page="${id}" aria-label="${label}" title="${label}">${icon(ic)}<span>${label}</span></button>`).join("");
  $$(".nav-button").forEach(b => b.onclick = () => showPage(b.dataset.page));
}
function showPage(id) {
  activePage = id; renderNav();
  $$(".page").forEach(p => p.classList.toggle("active", p.dataset.page === id));
  $("#page-title").textContent = compactMode ? "精簡控制" : pages.find(p=>p[0]===id)[1];
  $("#workspace").focus({preventScroll:true});
}
async function setMode(compact, resize=true) {
  compactMode = compact;
  localStorage.setItem("wvd-ui-mode", compact ? "compact" : "normal");
  document.body.classList.toggle("compact-mode", compact);
  const button=$("#mode-toggle");
  button.setAttribute("aria-pressed", String(compact));
  $("span",button).textContent=compact?"完整模式":"精簡模式";
  const controls=$("#compact-controls"), task=$(".current-task-block"), start=$("#start");
  if(compact)controls.append(task,button,start);
  else{$(".top-actions").prepend(button);$(".command-bar").append(task,start);showPage(activePage);}
  setRunning(state.running);
  if(resize)await api().set_window_mode(compact);
}
function render() {
  const c = state.config, categories = Object.keys(state.categories);
  const currentCategory = categories.find(name => Object.values(state.categories[name]).includes(c.FARM_TARGET)) || categories[0];
  $("#version").textContent = `CONTROL CENTER · ${state.version}`;
  $("#adb-mini").textContent = c.ADB_ADRESS || "尚未設定";
  $("#device-dot").style.background = c.EMU_PATH ? "var(--accent)" : "var(--amber)";
  $("#current-task").textContent = c.FARM_TARGET_TEXT || "尚未選擇";
  const strategies = c.STRATEGY || [];
  const strategyNames = strategies.map(x=>x.group_name);
  $("#workspace").innerHTML = `
    <div class="page" data-page="target">
      ${card("任務目標", "切換目標時會回到全域預設，避免沿用錯誤的任務設定。", `<div class="form-grid">${selectRaw("category", "任務類別", categories.map(x=>[x,x]), currentCategory)}<div class="field"><label for="FARM_TARGET">任務</label><select id="FARM_TARGET" name="FARM_TARGET"></select></div></div><label class="check-row" style="margin-top:13px"><input type="checkbox" name="TASK_SPECIFIC_CONFIG" ${c.TASK_SPECIFIC_CONFIG?"checked":""}><span>使用此任務專用的設定覆蓋全域預設</span></label><div class="toolbar"><button class="danger-button" id="clear-task">清除此任務設定</button></div>`)}
    </div>
    <div class="page" data-page="explore">
      ${card("探索與恢復", "控制寶箱、恢復、住宿與隊伍整理。", `${checks(["QUICK_DISARM_CHEST","DO_COMBAT_RECOVER","DO_CHEST_RECOVER","RECOVER_WHEN_BEGINNING","RECOVER_AFTER_REST","ACTIVE_REST","RE_ASSEMBLE_PARTY"])}<div class="form-grid" style="margin-top:13px">${select("WHO_WILL_OPEN_IT","開箱角色",[[0,"隨機"],[1,"左上"],[2,"中上"],[3,"右上"],[4,"左下"],[5,"中下"],[6,"右下"]])}${field("REST_INTERVEL","每幾次後住宿","number")}${field("RE_ASSEMBLE_PARTY_INTERVAL","每幾小時重置隊伍","number")}${select("KARMA_ADJUST","善惡調整",[["+0","維持現狀"],["+17","惡→中立／中立→善"],["-17","善→中立／中立→惡"]])}</div>`)}
    </div>
    <div class="page" data-page="timer">
      ${card("日常／週常", "到期項目會以琥珀色標示。", dailyHtml())}
    </div>
    <div class="page" data-page="combat">
      ${card("任務點策略", "全程使用單一方案，或為地下城中的每個任務點指定不同方案。", combatHtml(strategyNames))}
    </div>
    <div class="page" data-page="strategies">
      ${card("戰鬥方案", "方案會在重啟遊戲與角色死亡後重置。", `<div class="strategy-list" id="strategy-list">${strategies.map((s,i)=>strategyHtml(s,i)).join("")}</div><div class="toolbar"><button class="secondary-button" id="add-strategy">${icon("i-plus")} 新增方案</button></div>`)}
    </div>
    <div class="page" data-page="system">
      ${card("模擬器與 ADB", "支援 MuMu 與 BlueStacks 的既有執行流程。", `<div class="form-grid"><div class="field full"><label for="EMU_PATH">模擬器執行檔</label><div class="path-field"><input id="EMU_PATH" name="EMU_PATH" type="text" value="${esc(c.EMU_PATH||"")}"><button class="secondary-button" id="browse">瀏覽</button></div></div>${field("ADB_ADRESS","ADB 位址")}${field("EMU_INDEX","模擬器編號","number")}${select("LANGUAGE_SCRIPT","介面語言",[["zh_CN","简体中文"],["en_US","English"]],"重新啟動後生效")}${select("LANGUAGE_GAME","遊戲語言",[["zh_CN","简体中文"],["en_US","English"]],"需與模擬器中的遊戲一致")}</div>`)}
    </div>
    <div class="page" data-page="advanced">
      ${card("替代流程與因果", "只啟用你確定需要的替代流程。", checks(["ACTIVE_DIGGING","ACTIVE_BEG_MONEY","ACTIVE_FISHING","ACTIVE_ROYALSUITE_REST","ACTIVE_TRIUMPH","ACTIVE_BEAUTIFUL_ORE","ACTIVE_CSC","BYPASS_THE_WALL"]))}
      ${card("錯誤恢復門檻", "達到門檻時會依序重啟遊戲或模擬器。", `<div class="form-grid">${field("MAX_TRY_LIMIT","定位失敗幾次後重啟遊戲","number")}${field("MAX_CRASH_LIMIT","遊戲重啟幾次後重啟模擬器","number")}</div>`)}
    </div>
    <div class="page about-page" data-page="about">
      ${card("關於 WvDAS", "Wizardry Variants Daphne 自動化控制工具", `<div class="about-identity"><span class="brand-mark">W</span><div><h3>WvDAS</h3><p>為《Wizardry Variants Daphne》設計的開源自動化工具。</p></div></div><dl class="about-meta"><div><dt>版本</dt><dd>v${esc(state.version)}</dd></div><div><dt>作者</dt><dd>Dellyla（德德）</dd></div><div><dt>授權</dt><dd>GNU GPL v3.0</dd></div><div><dt>介面</dt><dd>Web UI · pywebview</dd></div></dl><div class="toolbar about-actions"><button class="secondary-button" data-url="https://github.com/arnold2957/wvd">${icon("i-code")} GitHub 專案</button><button class="ghost-button" id="show-changelog">${icon("i-info")} 更新日誌</button><button class="ghost-button" data-url="https://afdian.com/a/dellyla">${icon("i-heart")} 贊助作者</button></div>`, "about-card")}
      ${card("更新設定", "啟動時會自動檢查一次，也可隨時手動檢查。", `<div id="update-settings">${updateHtml()}</div>`, "about-card")}
    </div>`;
  wireControls(); setRunning(state.running); showPage(activePage); if(compactMode)$("#page-title").textContent="精簡控制";
}
function dailyHtml() { return `<div class="daily-grid"><button class="daily-action ${state.daily.webDue?"due":""}" data-url="https://store.wizardry.info/" data-daily="WEBSITE_ORG_TIME"><strong>領取 50 鑽（舊商店）</strong><small>${state.daily.webDue?"本週尚未領取":"本週已處理"}</small></button><button class="daily-action ${state.daily.webDue?"due":""}" data-url="https://webstore.wizardry.info/" data-daily="WEBSITE_ORG_TIME"><strong>領取 50 鑽（新商店）</strong><small>${state.daily.webDue?"本週尚未領取":"本週已處理"}</small></button><button class="daily-action ${state.daily.amDue?"due":""}" id="am-switch"><strong>切換至爐壺靈廟</strong><small>${state.daily.amDue?"雙週任務已刷新":"本期已處理"}</small></button></div>`; }
function combatHtml(names) {
  const opts = names.map(x=>[x,x]); let overall = state.config.DEFAULT_OVERALL_STRATEGY || names[0] || "全自动战斗";
  const saved = state.config.TASK_POINT_STRATEGY || {}; if(state.config.TASK_SPECIFIC_CONFIG && saved.overall_strategy) overall=saved.overall_strategy;
  if(state.taskPoints.length) opts.push(["自定义任务点策略","自訂任務點策略"]);
  const rows = state.taskPoints.map((p,i)=>select(`point-${i}`, p, names.map(x=>[x,x]))).join("");
  return `<div class="form-grid">${selectRaw("overall-strategy","全程策略",opts,overall)}<div class="field"><label>任務點數量</label><input value="${state.taskPoints.length}" disabled></div></div><div id="point-strategies" class="form-grid" style="margin-top:13px">${rows || "<p style='color:var(--muted)'>此任務沒有可設定的任務點。</p>"}</div>`;
}
function selectRaw(name,label,opts,value) { return `<div class="field"><label for="${name}">${label}</label><select id="${name}" name="${name}">${opts.map(([v,l])=>`<option value="${esc(v)}" ${v===value?"selected":""}>${esc(l)}</option>`).join("")}</select></div>`; }
function strategyHtml(s,i) { const rows=(s.skill_settings||[]).map((x,j)=>skillHtml(x,i,j)).join(""); return `<details class="strategy" data-strategy="${i}" ${i===0?"open":""}><summary><strong>${esc(s.group_name)}</strong><span>${(s.skill_settings||[]).length} 個角色</span></summary><div class="strategy-body"><div class="form-grid"><div class="field full"><label>方案名稱</label><input class="strategy-name" value="${esc(s.group_name)}" ${s.group_name==="全自动战斗"?"disabled":""}></div></div>${s.group_name==="全自动战斗"?"":`<div class="strategy-options"><label class="check-row"><input class="strategy-flag" data-key="need_reload_when_dungeon_begins" type="checkbox" ${s.need_reload_when_dungeon_begins?"checked":""}><span>進入地下城時重置</span></label><label class="check-row"><input class="strategy-flag" data-key="need_reload_when_combat_begins" type="checkbox" ${s.need_reload_when_combat_begins?"checked":""}><span>戰鬥開始前重置</span></label><label class="check-row"><input class="strategy-flag" data-key="complete_one_as_all" type="checkbox" ${s.complete_one_as_all?"checked":""}><span>任一技能釋放即視為完成</span></label></div><div class="skills">${rows}</div><div class="toolbar"><button class="ghost-button add-skill">${icon("i-plus")} 新增角色</button><button class="danger-button delete-strategy">${icon("i-trash")} 刪除方案</button></div>`}</div></details>`; }
function skillHtml(x,si,ri) { const charOpts=state.characters.map(c=>[c,c]); const skillOpts=["左上技能","右上技能","左下技能","右下技能","防御"].map(x=>[x,x]); return `<div class="skill-row" data-row="${ri}">${selectRaw("", "角色", charOpts, x.role_var)}${selectRaw("", "技能", skillOpts, x.skill_var)}${selectRaw("", "等級", [1,2,3,4,5,6,7].map(x=>[x,x]), x.skill_lvl||1)}<button class="icon-button delete-skill" aria-label="移除此角色" title="移除此角色">${icon("i-trash")}</button></div>`; }

function wireControls() {
  updateTargets(state.config.FARM_TARGET);
  $("#category").onchange = () => { updateTargets(); $("#FARM_TARGET").dispatchEvent(new Event("change")); };
  $("#FARM_TARGET").onchange = async e => { const o=e.target.selectedOptions[0]; state.config.FARM_TARGET=e.target.value; state.config.FARM_TARGET_TEXT=o.textContent; state.config.TASK_SPECIFIC_CONFIG=false; const details=await api().get_task_details(e.target.value); state.taskPoints=details.taskPoints||[]; render(); activePage="target"; showPage(activePage); markDirty(); if(details.tip)await appAlert(details.tip,"任務提示",{confirmText:"我了解了",wide:true}); };
  $$(`input[name], select[name]`).forEach(el => el.addEventListener("change", markDirty));
  $("#browse").onclick = async () => { const p=await api().select_emulator(); if(p){$("#EMU_PATH").value=p; markDirty();} };
  $("#clear-task").onclick = async () => { if(await appConfirm("確定刪除此任務的專用設定？")){await api().delete_task_config(state.config.FARM_TARGET); state=await api().get_state(); render(); toast({message:"任務設定已清除",type:"success"});} };
  $("#add-strategy").onclick = () => { state.config.STRATEGY.push({group_name:`策略配置 ${state.config.STRATEGY.length}`,skill_settings:[]}); render(); activePage="strategies"; showPage(activePage); markDirty(); };
  $$(".add-skill").forEach(b=>b.onclick=()=>{const i=+b.closest(".strategy").dataset.strategy;state.config.STRATEGY[i].skill_settings.push({role_var:state.characters[0],skill_var:"左上技能",target_var:"不可用",skill_lvl:1});render();activePage="strategies";showPage(activePage);markDirty();});
  $$(".delete-strategy").forEach(b=>b.onclick=async()=>{const i=+b.closest(".strategy").dataset.strategy;if(await appConfirm("確定刪除此戰鬥方案？")){state.config.STRATEGY.splice(i,1);render();activePage="strategies";showPage(activePage);markDirty();}});
  $$(".delete-skill").forEach(b=>b.onclick=()=>{const d=b.closest(".strategy"), r=b.closest(".skill-row");state.config.STRATEGY[+d.dataset.strategy].skill_settings.splice(+r.dataset.row,1);render();activePage="strategies";showPage(activePage);markDirty();});
  $$("[data-url]").forEach(b=>b.onclick=async()=>{await api().open_url(b.dataset.url);if(b.dataset.daily)await api().mark_daily(b.dataset.daily);b.classList.remove("due");});
  const changelog=$("#show-changelog"); if(changelog) changelog.onclick=showChangelog;
  const am=$("#am-switch"); if(am) am.onclick=()=>{for(const [cat,quests] of Object.entries(state.categories)){for(const [name,code] of Object.entries(quests)){if(name.includes("炉壶灵庙")){state.config.FARM_TARGET=code;state.config.FARM_TARGET_TEXT=name;state.config.AM_REFRESH_TIME=new Date().toISOString().slice(0,10);api().mark_daily("AM_REFRESH_TIME");render();markDirty();return;}}}};
  wireUpdateControls();
}
function updateTargets(value) { const cat=$("#category").value || Object.keys(state.categories)[0], target=$("#FARM_TARGET"), entries=Object.entries(state.categories[cat]||{}); target.innerHTML=entries.map(([name,code])=>`<option value="${esc(code)}" ${code===(value||state.config.FARM_TARGET)?"selected":""}>${esc(name)}</option>`).join(""); if(!target.value&&entries.length)target.value=entries[0][1]; }
function collect() {
  const c={...state.config}; $$(`input[name], select[name]`).forEach(el=>{if(el.name==="category")return;c[el.name]=el.type==="checkbox"?el.checked:el.type==="number"?Number(el.value):el.value;});
  const target=$("#FARM_TARGET"); if(target){c.FARM_TARGET=target.value;c.FARM_TARGET_TEXT=target.selectedOptions[0]?.textContent||"";}
  c.STRATEGY=$$(".strategy").map((d,i)=>{const old=state.config.STRATEGY[i], skills=$$(".skill-row",d).map(r=>{const sels=$$("select",r);return {role_var:sels[0].value,skill_var:sels[1].value,target_var:"不可用",freq_var:"",skill_lvl:Number(sels[2].value)}}); const result={...old,group_name:$(".strategy-name",d).value,skill_settings:skills}; $$(".strategy-flag",d).forEach(x=>result[x.dataset.key]=x.checked); return result;});
  const overall=$("#overall-strategy"); if(overall){const points={}; $$(`[name^="point-"]`).forEach((x,i)=>points[i]=x.value);c.TASK_POINT_STRATEGY={overall_strategy:overall.value,task_point:points};if(!c.TASK_SPECIFIC_CONFIG)c.DEFAULT_OVERALL_STRATEGY=overall.value;}
  return c;
}
async function save() { const c=collect(), r=await api().save(c); if(r.ok){state.config=c;dirty=false;toast({message:"設定已儲存",type:"success"});}else toast({message:r.error,type:"error"}); return r.ok; }
function markDirty(){dirty=true;$("#save").style.color="var(--accent)";}
function setRunning(on){state.running=on;const s=$("#run-state"),b=$("#start");s.classList.toggle("running",on);s.lastElementChild.textContent=on?"執行中":"待命";b.classList.toggle("stop",on);b.innerHTML=icon(on?"i-stop":"i-play")+`<span>${on?"停止任務":compactMode?"繼續任務":"啟動腳本"}</span>`;$$(`input,select,.secondary-button,.danger-button,.ghost-button`).forEach(x=>{if(!x.closest(".telemetry, .about-page")&&x.id!=="auto-update")x.disabled=on;});}
window.setRunning=setRunning;
window.appendLog=line=>{const d=document.createElement("div");d.className="log-line";d.textContent=line;const l=$("#logs");l.append(d);while(l.children.length>500)l.firstChild.remove();l.scrollTop=l.scrollHeight;};
window.setSummary=text=>$("#summary").textContent=text;
window.toast=({message,type=""})=>{const t=$("#toast");t.textContent=message;t.className=`show ${type}`;clearTimeout(t.timer);t.timer=setTimeout(()=>t.className="",3500);};
window.showUpdate=data=>{const wasManual=manualUpdateCheck;updateData=data;checkingUpdate=false;updateCheckError=false;manualUpdateCheck=false;if(state){state.config.LATEST_VERSION=data.version;renderUpdatePanel();if(wasManual)toast({message:`發現新版本 v${data.version}`,type:"success"});notifyUpdate(data);}};
window.updateCurrent=data=>{const wasManual=manualUpdateCheck;updateData=null;checkingUpdate=false;updateCheckError=false;manualUpdateCheck=false;if(state){state.config.LATEST_VERSION=data.version;renderUpdatePanel();if(wasManual)toast({message:"目前已是最新版本",type:"success"});}};
window.updateCheckFailed=message=>{const wasManual=manualUpdateCheck;checkingUpdate=false;updateCheckError=true;manualUpdateCheck=false;if(state){renderUpdatePanel();if(wasManual)toast({message,type:"error"});}};
window.updateDownload=data=>{const p=$(".progress");if(!p)return;p.hidden=false;if(data.total)p.dataset.total=data.total;const total=Number(p.dataset.total||1);$("i",p).style.width=`${Math.min(100,(data.current||0)/total*100)}%`;};
window.questSwitched=async()=>{state=await api().get_state();render();};
function finishStartup() {
  if (updateData) notifyUpdate(updateData);
}
let pollingEvents = false;
async function pollEvents() {
  if (pollingEvents) return;
  pollingEvents = true;
  try {
    for (const event of await api().poll_events()) {
      const handler = window[event.command];
      if (typeof handler === "function") handler(event.value);
    }
  } catch (error) {
    console.error("Unable to poll application events", error);
  } finally {
    pollingEvents = false;
  }
}
async function bootstrap() {
  try {
    window.alert = appAlert;
    window.confirm = appConfirm;
    state = await api().get_state();
    renderNav();
    render();
    await setMode(compactMode);
    $("#mode-toggle").onclick = () => setMode(!compactMode);
    $("#save").onclick = save;
    $("#clear-log").onclick = () => $("#logs").replaceChildren();
    $("#start").onclick = async () => {
      if (state.running) {
        await api().stop_task();
        return;
      }
      const config = collect();
      const result = await api().start_task(config);
      if (result.ok) {
        state.config = config;
        setRunning(true);
      } else {
        toast({message:result.error, type:"error"});
      }
    };
    initializing = false;
    setInterval(pollEvents, 200);
    void pollEvents();
    setTimeout(finishStartup, 0);
  } catch (error) {
    initializing = false;
    await appAlert(`介面初始化失敗：${error?.message || error}`, "啟動失敗");
  }
}
window.addEventListener("pywebviewready", () => { void bootstrap(); });
window.addEventListener("beforeunload",e=>{if(dirty&&!state?.running){e.preventDefault();e.returnValue="";}});
