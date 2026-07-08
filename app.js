let KB=null, CUR="all", Q="", INDEX=[];
let SEARCH={};   // id -> 全文检索文本（kb_search.json 异步加载后填充）
let listScroll=0, listShown=0;   // 打开文章前列表的滚动位置/已渲染卡片数，返回时恢复
// 数据文件基址：主站在根目录=''；文章静态页(a/<id>.html)里会被置为 '../' 以回到根目录取数据
const DATA_BASE = (typeof window!=='undefined' && window.DATA_BASE) || '';
// 站点根目录路径（含末尾/）：在文章页 /.../a/x.html 里要去掉末尾的 a/，回到站点根，
// 供拼接分享链接、admin.html 等站点级地址用。
function siteRoot(){
  let dir=location.pathname.replace(/[^/]*$/,'');   // 去掉文件名，留目录
  if(/\/a\/$/.test(dir)) dir=dir.replace(/a\/$/,''); // 文章页在 a/ 子目录 → 回退到根
  return dir;
}
const $=s=>document.querySelector(s);
const esc=s=>(s||"").replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// ===== Edge Function 鉴权层（写操作走服务端，前端不碰 service_role）=====
// Supabase 项目地址（公开，非密钥）。弃用 anon key 后 SB 对象已删，
// 这里若再引用 SB 会在顶层 const 求值时抛 ReferenceError，导致整个脚本
// 中断、boot() 永不执行、加载遮罩永久转圈（首页打不开的真凶）。
const API_BASE='https://cddkniwbhvcbfgkgomtl.supabase.co/functions/v1/admin-api';
const API_TOKEN_KEY='ab_kb_api_token';
function apiToken(){try{return localStorage.getItem(API_TOKEN_KEY)||'';}catch(e){return '';}}
function apiSetToken(t){try{localStorage.setItem(API_TOKEN_KEY,t||'');}catch(e){}}
// 用访问码换令牌（成功返回 true）
async function apiLogin(pin){
  const r=await fetch(API_BASE+'/login',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})});
  if(!r.ok) return false;
  const d=await r.json().catch(()=>({}));
  if(d&&d.token){apiSetToken(d.token);return true;}
  return false;
}
// 带令牌写文章（POST /article，upsert）；令牌过期抛错提示重登
async function apiWriteArticle(row){
  const r=await fetch(API_BASE+'/article',{method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+apiToken()},
    body:JSON.stringify({row})});
  if(r.status===401){apiSetToken('');throw new Error('登录已过期，请重新输入访问码');}
  const d=await r.json().catch(()=>({}));
  if(!r.ok||!d.ok) throw new Error('写入失败 '+r.status+' '+JSON.stringify(d).slice(0,120));
  return d.data;
}

function buildIndex(){
  // 检索文本：优先用已加载的全文(SEARCH[id] 或 d.text)，否则用摘要 excerpt。
  // 全文索引(kb_search.json)后台加载完后会重建一次，届时升级为正文全文搜索。
  INDEX=KB.docs.map(d=>{
    const full=SEARCH[d.id]!==undefined?SEARCH[d.id]:(d.text||d.excerpt||'');
    return {d, t:(d.title+' '+(d.keywords||'')+' '+full).toLowerCase()};
  });
}
function applyKB(kb){
  KB=kb;
  // 【形态二】文章静态页自带本篇正文时（window.INIT_MD），将正文直接就地注入到对应 doc.md，
  // 以便 openDoc → getMd 命中 `if(d && d.md) return d.md`，直达无需再 fetch kb_docs.json。
  if(typeof window!=='undefined' && window.INIT_MD && window.INIT_DOC){
    const d=KB.docs&&KB.docs.find(x=>x.id===+window.INIT_DOC);
    if(d && !d.md) d.md=window.INIT_MD;
  }
  buildIndex();
  renderCats(); renderFoot();
  // 若要直达某篇（文章静态页），首屏不先渲染列表，避免"列表闪一下再跳文章"
  if(PENDING_DOC) return;
  // 若正停在列表页则重渲染（阅读态不打断用户）
  if(!document.querySelector('.reader')) render();
}

// 直达目标：文章静态页注入 window.INIT_DOC；否则看 URL #doc=<id>。boot 前先定，供 applyKB 判断。
const PENDING_DOC = (()=>{
  if(typeof window!=='undefined'&&window.INIT_DOC) return +window.INIT_DOC;
  const m=/#doc=(\d+)/.exec(location.hash||''); return m?+m[1]:0;
})();

// 带超时的 fetch：任一请求挂起(国内访问 GitHub Pages 偶发)不会让首屏无限转圈，
// 超时即抛错走下一个回退路径。默认 8 秒。
async function fetchT(url, ms=8000){
  const ctl=new AbortController();
  const t=setTimeout(()=>ctl.abort(), ms);
  try{ return await fetch(url,{signal:ctl.signal}); }
  finally{ clearTimeout(t); }
}
// 数据文件 URL：带分钟级 cache-bust。kb_*.json 在 GitHub Pages 上带 CDN/浏览器缓存(max-age=600)，
// 不破缓存的话后台改动后最多要等 10 分钟才可见（妙搭薄壳、以及已打开过首页的浏览器都吃旧缓存）。
// 用「分钟」做 ?v= key：同一分钟内同 URL → 命中缓存(每分钟至多回源一次，不打爆 Pages)；跨分钟即取新 →
// 本站(DATA_BASE='')读取最新数据。
function dataUrl(name){ return DATA_BASE+name+'?v='+Math.floor(Date.now()/600000); }

async function boot(){
  marked.setOptions({breaks:true, gfm:true});
  let shown=false;
  // 纯静态：只读静态内容，不连数据库。静态文件由数据库变化触发 Action 重新生成。
  // 1) 首屏只下轻量列表 kb_index.json（无正文，几百KB → 快）；正文点开时按需拉
  try{
    const r=await fetchT(dataUrl('kb_index.json'));
    if(r.ok){
      const idx=await r.json();
      if(idx&&idx.docs&&idx.docs.length){ applyKB(idx); shown=true; }
    }
  }catch(e){}
  // 2) 回退：完整 kb_cache.json（含正文）
  if(!shown){
    try{
      const r=await fetchT(dataUrl('kb_cache.json'), 15000);
      if(r.ok){ const c=await r.json(); if(c&&c.docs&&c.docs.length){ applyKB(c); shown=true; } }
    }catch(e){}
  }
  // 3) 回退：打包内嵌数据（standalone 离线可用）
  if(!shown){
    try{
      const embed=document.getElementById('kbdata');
      const raw=embed?embed.textContent.trim():'';
      if(raw && raw[0]==='{'){ applyKB(JSON.parse(raw)); shown=true; }
      else{ const r=await fetchT(dataUrl('kb.json'), 15000); applyKB(await r.json()); shown=true; }
    }catch(e){}
  }
  if(!shown){ $('#loading').innerHTML='<div class="ld-t">加载失败，请刷新重试</div><div class="ld-s">可能是网络问题，请检查能否访问 GitHub</div>'; return; }
  // 直达某篇：先把文章渲染好再显示 #app（await 正文加载完），彻底不闪列表；
  // 目标文章不存在（已下线/删除）时回退列表
  if(PENDING_DOC && KB.docs.some(d=>d.id===PENDING_DOC)) await openDoc(PENDING_DOC);
  else if(PENDING_DOC) render();
  $('#loading').style.display='none'; $('#app').style.display='grid';
  setupSubmit();
  // 修正管理后台入口：文章页在 a/ 子目录，相对 admin.html 会指到 a/admin.html，用站点根拼绝对路径
  const al=$('#adminLink'); if(al) al.href=siteRoot()+'admin.html';
  // 首屏已出。若走的是轻量列表(docs 无全文)，后台异步加载全文检索索引，
  // 加载完重建 INDEX——此后搜索从"标题+摘要"升级为"正文全文"。不阻塞首屏。
  loadSearchIndex();
}

async function loadSearchIndex(){
  if(KB && KB.docs && KB.docs[0] && KB.docs[0].text!==undefined) return; // 已含全文(cache/embed 路径)
  try{
    const r=await fetchT(dataUrl('kb_search.json'), 20000);
    if(!r.ok) return;
    SEARCH=await r.json();
    buildIndex();               // 用全文重建检索索引
    if(Q && !document.querySelector('.reader')) render();  // 用户已在搜且停列表 → 用全文重刷结果
  }catch(e){}
}

// 写文章提交：页面纯静态读取，但提交直接写 Supabase（之后由 Action 重生成静态文件同步）
function setupSubmit(){
  $('#edSubmit').style.display='';
  $('#edHint').innerHTML='';
}

function renderFoot(){
  const total=KB.docs.length;
  const cats=KB.categories.filter(c=>KB.docs.some(d=>d.cat===c.key)).length;
  // 最近更新日期
  const dates=KB.docs.map(d=>d.updated).filter(Boolean).sort();
  const latest=dates.length?dates[dates.length-1]:'';
  $('#sideFoot').innerHTML=`
    <div class="sf-stat">
      <div class="sf-pill"><b>${total}</b><span>篇知识</span></div>
      <div class="sf-pill"><b>${cats}</b><span>大主题</span></div>
    </div>
    <div class="sf-line"><span class="sf-dot"></span>知识库在线 · 最近更新 ${latest||'—'}</div>`;
}

function counts(){
  const m={all:KB.docs.length};
  KB.categories.forEach(c=>m[c.key]=0);
  KB.docs.forEach(d=>m[d.cat]=(m[d.cat]||0)+1);
  return m;
}
function renderCats(){
  const m=counts();
  let h=`<div class="cat ${CUR==='all'?'on':''}" data-k="all">
    <span class="ic">📚</span><span class="nm">全部知识</span><span class="ct">${m.all}</span></div>`;
  KB.categories.forEach(c=>{
    if(!m[c.key]) return;
    h+=`<div class="cat ${CUR===c.key?'on':''}" data-k="${c.key}" title="${esc(c.desc)}">
      <span class="ic">${c.icon}</span><span class="nm">${esc(c.name)}</span><span class="ct">${m[c.key]}</span></div>`;
  });
  $('#cats').innerHTML=h;
  document.querySelectorAll('.cat').forEach(el=>el.onclick=()=>{
    CUR=el.dataset.k; renderCats(); render(); closeSide();
    $('#bodyView').scrollTop=0;
  });
}

function match(){
  let arr=INDEX;
  if(CUR!=='all') arr=arr.filter(x=>x.d.cat===CUR);
  if(Q){
    const terms=Q.toLowerCase().split(/\s+/).filter(Boolean);
    arr=arr.filter(x=>terms.every(t=>x.t.includes(t)));
    // 标题命中优先
    arr=[...arr].sort((a,b)=>{
      const at=a.d.title.toLowerCase(), bt=b.d.title.toLowerCase();
      const as=terms.some(t=>at.includes(t))?1:0, bs=terms.some(t=>bt.includes(t))?1:0;
      return bs-as;
    });
  }else{
    // 不搜索时：按更新日期倒序（新发布的在最上面），同日期内部文章优先
    arr=[...arr].sort((a,b)=>{
      const au=a.d.updated||'', bu=b.d.updated||'';
      if(au!==bu) return bu<au?-1:1;                    // 日期新的在前
      return (b.d.internal?1:0)-(a.d.internal?1:0);      // 同日期内部文章优先
    });
  }
  return arr.map(x=>x.d);
}
function catOf(k){return KB.categories.find(c=>c.key===k)||{icon:'📎',name:'其他'};}

function hi(text){
  if(!Q) return esc(text);
  let h=esc(text);
  Q.toLowerCase().split(/\s+/).filter(Boolean).forEach(t=>{
    if(!t)return;
    const re=new RegExp('('+t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','ig');
    h=h.replace(re,'<mark>$1</mark>');
  });
  return h;
}
function docText(d){ return SEARCH[d.id]!==undefined?SEARCH[d.id]:(d.text||''); }
function excerpt(d){
  if(Q){
    // 搜索时：若已有全文，截取命中词附近片段；否则用已有摘要
    const t=docText(d);
    if(t){
      const low=t.toLowerCase(), term=Q.toLowerCase().split(/\s+/)[0];
      const i=low.indexOf(term);
      if(i>=0){const s=Math.max(0,i-40);return (s>0?'…':'')+t.slice(s,s+140)+'…';}
    }
  }
  return (d.excerpt!==undefined?d.excerpt:(d.text||'').slice(0,140))+'…';
}

const PAGE=12;                 // 每批渲染卡片数（手机约2屏，分批更多、加载更可感知）
let RES=[], SHOWN=0, IO=null;  // 当前结果集 / 已渲染数 / 滚动观察器
function cardHTML(d){
  const c=catOf(d.cat);
  return `<div class="card" data-id="${d.id}">
      <h3>${hi(d.title)}</h3>
      <div class="excerpt">${hi(excerpt(d))}</div>
      <div class="meta">
        <span class="ct-tag">${c.icon} ${esc(c.name)}</span>
        <span class="mdot">📄 ${(d.len!==undefined?d.len:(d.text||'').length).toLocaleString()} 字</span>
        ${d.updated?`<span class="mdot">🕐 ${d.updated}</span>`:''}
        <span class="src">阅读 →</span>
      </div></div>`;
}
function bindCards(scope){
  (scope||document).querySelectorAll('.card:not([data-bound])').forEach(el=>{
    el.dataset.bound='1'; el.onclick=()=>openDoc(+el.dataset.id);
  });
}
let LOADING=false;
function _appendBatch(){
  const list=$('#kbList'); if(!list) return;
  const start=SHOWN;
  const next=RES.slice(SHOWN, SHOWN+PAGE);
  list.insertAdjacentHTML('beforeend', next.map(cardHTML).join(''));
  SHOWN+=next.length; bindCards(list);
  // 让本批新卡片错落淡入（可见的瀑布流效果）；
  // .new 期间 pointer-events:none屏蔽点击，动画结束后移除 .new 开启点击。
  const cards=list.querySelectorAll('.card');
  for(let i=start;i<SHOWN;i++){
    const el=cards[i];
    if(!el) continue;
    el.classList.add('new');
    el.style.animationDelay=((i-start)*55)+'ms';
    el.addEventListener('animationend',function _rm(ev){
      // 只响应入场动画，不误伤其它可能的子元素动画
      if(ev && ev.animationName && ev.animationName!=='cardIn') return;
      el.classList.remove('new');
      el.removeEventListener('animationend', _rm);
    });
    // 兵底：若因某种原因 animationend 未触发，兽定时器到时强行开启点击
    setTimeout(()=>el.classList.remove('new'), 900);
  }
  const sen=$('#sentinel');
  if(sen){
    sen.className='loadmore-wrap'; sen.removeAttribute('style');
    if(SHOWN>=RES.length){
      sen.innerHTML='<div class="loadmore done">— 已显示全部 '+RES.length+' 篇 —</div>';
    }else{
      sen.innerHTML='<div class="loadmore"><span class="dot"></span>正在加载更多（'+SHOWN+' / '+RES.length+'）</div>';
    }
  }
}
// first=true 为首批（立即渲染，秒开）；滚动触发的批次先显示“加载中”停顿一下再出，让用户看得见
function renderMore(first){
  if(LOADING) return;
  if(first){ _appendBatch(); return; }
  if(SHOWN>=RES.length) return;
  LOADING=true;
  const sen=$('#sentinel');
  if(sen){ sen.className='loadmore-wrap'; sen.innerHTML='<div class="loadmore"><span class="dot"></span>正在加载更多…</div>'; }
  setTimeout(()=>{ _appendBatch(); LOADING=false; }, 480);
}
function render(){
  RES=match(); SHOWN=0;
  if(IO){ IO.disconnect(); IO=null; }
  $('#stat').innerHTML = Q
    ? `找到 <b>${RES.length}</b> 篇匹配「${esc(Q)}」的知识`
    : `共 <b>${RES.length}</b> 篇 · 全库 <b>${KB.docs.length}</b> 篇 · 每篇可溯源至官方原文`;
  const v=$('#bodyView');
  if(!RES.length){
    v.innerHTML=`<div class="empty"><div class="big">🔍</div>没有找到相关内容，换个关键词试试</div>`;return;
  }
  v.innerHTML=`<div class="list" id="kbList"></div><div id="sentinel" style="height:1px"></div>`;
  renderMore(true);  // 首批立即渲染（秒开）
  // 滚动到底自动加载下一批
  const sen=$('#sentinel');
  if(sen && SHOWN<RES.length){
    IO=new IntersectionObserver(es=>{ if(es[0].isIntersecting) renderMore(); }, {root:v, rootMargin:'80px'});
    IO.observe(sen);
  }
  return;
}

// 正文按需加载：轻量列表无 md，点开文章时从 kb_docs.json 取（取一次缓存整份）
let DOCS_CACHE=null;
async function getMd(id){
  const d=KB.docs.find(x=>x.id===id);
  if(d && d.md) return d.md;                    // 已有正文（内嵌/完整版）
  if(!DOCS_CACHE){
    try{ const r=await fetchT(dataUrl('kb_docs.json'), 20000); if(r.ok) DOCS_CACHE=await r.json(); }
    catch(e){ DOCS_CACHE={}; }
  }
  return (DOCS_CACHE&&DOCS_CACHE[String(id)])||'（正文加载失败，请刷新重试）';
}

// 把正文里“相邻的多张图”并排成一行(.imrow)。
// marked(breaks:true) 会把连续图片行渲染成 <img><br><img>，需按同级相邻 img 分组。
function groupImages(scope){
  const md=(scope||document).querySelector('.md'); if(!md) return;
  const imgs=[...md.querySelectorAll('img')];
  const seen=new Set();
  imgs.forEach(img=>{
    if(seen.has(img)) return;
    // 收集与该 img 同父、仅被 <br> 或空白文本隔开的连续 img
    const run=[img]; let n=img.nextSibling;
    while(n){
      if(n.nodeType===3 && !n.textContent.trim()){ n=n.nextSibling; continue; }
      if(n.nodeType===1 && n.tagName==='BR'){ n=n.nextSibling; continue; }
      if(n.nodeType===1 && n.tagName==='IMG'){ run.push(n); n=n.nextSibling; continue; }
      break;
    }
    if(run.length>=2){
      const row=document.createElement('div'); row.className='imrow';
      img.parentNode.insertBefore(row, img);
      // 移走这些 img 及它们之间的 <br>
      run.forEach((im,idx)=>{
        let br=im.nextSibling;
        row.appendChild(im); seen.add(im);
        // 清掉紧跟的 <br>（并排后不需要换行）
        while(br && ((br.nodeType===1&&br.tagName==='BR')||(br.nodeType===3&&!br.textContent.trim()))){
          const del=br; br=br.nextSibling; if(del.parentNode) del.parentNode.removeChild(del);
        }
      });
    } else { seen.add(img); }
  });
}

let _docSeq=0;
async function openDoc(id, opts){
  opts=opts||{};
  const d=KB.docs.find(x=>x.id===id); if(!d)return;
  const c=catOf(d.cat);
  const v=$('#bodyView');
  // 打开文章前，若当前是列表视图，记住其滚动位置，返回时恢复
  if(!v.querySelector('.reader')){ listScroll=v.scrollTop; listShown=SHOWN; }
  const isInternal = d.internal || !/^https?:/.test(d.url||'');
  const srcFoot = isInternal
    ? '本文为营销增长中心内部沉淀'
    : '内容整理自火山引擎 DataTester A/B testing 文档库';
  // 【体感优化】：先立即渲染外壳(标题/meta/返回按钮)+ 正文加载占位,秒切页面消除假死感;
  // 正文异步获取(首次点开需拉 kb_docs.json ~2MB),加载完再填充 .md 区。
  const seq = (++_docSeq);
  v.innerHTML=`<div class="reader">
    <div class="rtop">
      <span class="rlink" id="rback">← 返回列表</span>
      <span class="rlink" id="copyLink" data-id="${d.id}">复制链接</span>
    </div>
    <article class="rhead">
      <h1>${esc(d.title)}</h1>
      <div class="rmeta">
        <span class="ct-tag">${c.icon} ${esc(c.name)}</span>
        <span>📄 ${(d.len!==undefined?d.len:(d.text||'').length).toLocaleString()} 字</span>
        ${d.updated?`<span>🕐 ${d.updated}</span>`:''}
      </div>
    </article>
    <div class="md" id="mdBody"><div class="md-loading"><div class="spin"></div><div>正在加载正文…</div></div></div>
    <div class="rfoot">${srcFoot}</div>
  </div>`;
  v.scrollTop=0;
  // 异步取正文并填充(带 seq 竞态守卫:用户快速切换文章时,老请求返回后不再覆盖新页面)
  (async()=>{
    let md=await getMd(id);
    if(seq!==_docSeq) return;  // 已切到别的文章,丢弃本次结果
    md=(md||'').replace(/^\s*#\s+.*(?:\r?\n)+/, '');
    const html=marked.parse(md);
    const mdEl=$('#mdBody');
    if(mdEl){ mdEl.innerHTML=html; groupImages(v); }
  })();
  // 地址栏换成真实静态页地址 a/<id>.html（pushState，不刷新页面）：地址真实可分享、可后退。
  // 文章静态页(a/<id>.html，注入 INIT_DOC)首次打开自己那篇时地址已对，不再 push；
  // 由浏览器后退(popstate)触发的打开也不 push（opts.push=false）。file:// 本地无法 pushState 跳目录，降级 hash。
  const onArticlePage = (typeof window!=='undefined' && window.INIT_DOC);
  if(opts.push!==false && location.protocol!=='file:'){
    const target=siteRoot()+'a/'+id+'.html';
    try{ if(location.pathname!==new URL(target,location.href).pathname) history.pushState({doc:id},'',target); }catch(e){}
  }else if(location.protocol==='file:' && !onArticlePage){
    try{ if(location.hash!=='#doc='+id) history.replaceState(null,'','#doc='+id); }catch(e){}
  }
  $('#rback').onclick=()=>backToList(true);
  const cl=$('#copyLink');
  if(cl) cl.onclick=async()=>{
    // 复制的是真实静态页地址（可分享、可被搜索引擎收录）；本地 file:// 打开时回退 hash
    const url=location.protocol==='file:'
      ? location.origin+location.pathname+'#doc='+cl.dataset.id
      : location.origin+siteRoot()+'a/'+cl.dataset.id+'.html';
    let ok=false;
    try{ await navigator.clipboard.writeText(url); ok=true; }
    catch(e){
      try{ const ta=document.createElement('textarea'); ta.value=url; ta.style.position='fixed'; ta.style.opacity='0';
        document.body.appendChild(ta); ta.select(); ok=document.execCommand('copy'); ta.remove(); }catch(_){}
    }
    const old=cl.innerHTML;
    cl.innerHTML = ok ? '已复制' : '复制失败';
    cl.classList.add('copied');
    setTimeout(()=>{ cl.innerHTML=old; cl.classList.remove('copied'); }, 1800);
  };
}

// 返回列表：切回列表视图并恢复浏览位置。push=true 时把地址栏推回首页（供“返回”按钮用）；
// 文章静态页(INIT_DOC)上没有内存里的列表来路，直接整页跳根目录首页。
function backToList(push){
  if(typeof window!=='undefined' && window.INIT_DOC){ location.href=siteRoot(); return; }
  if(push && location.protocol!=='file:'){ try{ history.pushState({list:1},'',siteRoot()); }catch(e){} }
  else if(push){ try{ history.replaceState(null,'',location.pathname+location.search); }catch(e){} }
  render();
  // 同步补齐返回前已展开的批数（renderMore 非首批是 480ms 异步+LOADING 锁，while 里补不动，
  // 会导致列表高度不够、scrollTop 恢复失败回到顶部）。直接同步 _appendBatch 补够高度。
  while(SHOWN<listShown && SHOWN<RES.length) _appendBatch();
  // 高度补足后立即定位（无 smooth，瞬间到位，不出现滚动过程）
  const bv=$('#bodyView'); if(bv) bv.scrollTop=listScroll;
}
// 浏览器前进/后退：地址是 a/<id>.html → 打开该篇；否则回列表。均不再 push（避免历史循环）。
window.addEventListener('popstate',()=>{
  if(!KB) return;
  const m=/\/a\/(\d+)\.html$/.exec(location.pathname);
  if(m && KB.docs.some(d=>d.id===+m[1])) openDoc(+m[1],{push:false});
  else backToList(false);
});

// 搜索
$('#q').addEventListener('input',e=>{
  Q=e.target.value.trim();
  $('#clr').style.display=Q?'block':'none';
  render();
});
$('#clr').onclick=()=>{$('#q').value='';Q='';$('#clr').style.display='none';render();$('#q').focus();};
// 移动端
function closeSide(){$('#aside').classList.remove('open');$('#mmask').classList.remove('on');}
$('#mtoggle').onclick=()=>{$('#aside').classList.toggle('open');$('#mmask').classList.toggle('on');};
$('#mmask').onclick=closeSide;

/* ===== 写文章编辑器 ===== */
// ===== 写文章访问控制 =====
const AUTH_KEY='ab_kb_auth_ts', AUTH_TTL=2*3600*1000; // 对齐 EdgeFn JWT TTL(2h)
function loggedIn(){
  try{const ts=+localStorage.getItem(AUTH_KEY); return ts && (Date.now()-ts)<AUTH_TTL;}catch(e){return false;}
}
// 点「写文章」：已授权直接进；否则先验证
function requireAuthThenEdit(){
  if(loggedIn()){ openEditor(); return; }
  $('#loginErr').textContent='';
  $('#loginPin').value='';
  $('#loginMask').classList.add('on');
  setTimeout(()=>$('#loginPin').focus(),50);
}
async function doLogin(){
  const pin=$('#loginPin').value.trim();
  const err=$('#loginErr');
  if(!pin){ err.textContent='请输入访问码'; return; }
  err.textContent='校验中…';
  try{
    // 服务端校验访问码 → 拿令牌（口令与 service_role 都在 Edge Function 环境变量）
    const ok=await apiLogin(pin);
    if(ok){
      try{localStorage.setItem(AUTH_KEY,String(Date.now()));}catch(e){}
      $('#loginMask').classList.remove('on');
      openEditor();
    }else{ err.textContent='访问码不正确'; }
  }catch(e){ err.textContent='网络错误，请稍后重试'; }
}

function openEditor(){
  // 填充分类下拉（所有分类都可选，默认选 cases 实战案例库）
  const sel=$('#edCat');
  if(!sel.options.length){
    KB.categories.forEach(c=>{
      const o=document.createElement('option');
      o.value=c.key; o.textContent=`${c.icon} ${c.name}`;
      sel.appendChild(o);
    });
    sel.value='cases';
  }
  $('#editor').classList.add('on'); $('#editorMask').classList.add('on');
  updatePrev(); closeSide();
}
function closeEditor(){$('#editor').classList.remove('on');$('#editorMask').classList.remove('on');}
function edData(){
  return {
    title:$('#edTitle').value.trim(),
    cat:$('#edCat').value,
    kw:$('#edKw').value.trim(),
    md:$('#edMd').value
  };
}
function updatePrev(){
  const d=edData(); const c=catOf(d.cat);
  $('#edPrevTag').innerHTML=`${c.icon} ${esc(c.name)}`;
  $('#edPrevTitle').textContent=d.title||'（未填标题）';
  $('#edPrevBody').innerHTML=marked.parse(d.md||'*在左侧输入 Markdown，这里实时预览…*');
}
function edMsg(cls,txt){const m=$('#edMsg');m.className='ed-msg '+cls;m.textContent=txt;}
function plainText(md){
  return (md||'').replace(/!\[[^\]]*\]\([^)]*\)/g,'').replace(/<[^>]+>/g,'')
    .replace(/```[\s\S]*?```/g,'').replace(/[#>*`|\-]{1,}/g,' ').replace(/\s+/g,' ').trim();
}
// 直接写入 Supabase，返回写入的行（含生成的 id，供本地内存同步复用同一 id）
async function submitToDB(d){
  const today=new Date().toISOString().slice(0,10);
  const row={
    doc_id: 910000000+Date.now()%90000000,   // 内部文章用9开头唯一id
    title:d.title, cat:d.cat, keywords:(d.kw+' 内部文章').trim(),
    md:d.md, body_text:plainText(d.md), updated:today,
    source_url:'', is_internal:true
  };
  // 走 Edge Function 带令牌写（服务端用 service_role 落库），前端不再持写权限
  await apiWriteArticle(row);
  return row;
}
async function submitArticle(){
  const d=edData();
  if(!d.title){edMsg('err','请先填写标题');return;}
  if(!d.md.trim()){edMsg('err','正文不能为空');return;}
  const btn=$('#edSubmit'); btn.disabled=true;
  edMsg('load','正在发布，请稍候…');
  try{
    const row=await submitToDB(d);
    // 纯静态：不回连数据库。用刚写库的 row（同一 id）插入内存，让提交者当场看到；
    // 线上静态文件由数据库变化触发 GitHub Action 重新生成。
    const newId=row.doc_id;
    KB.docs.push({id:newId,title:d.title,cat:d.cat,
      keywords:row.keywords,md:d.md,text:row.body_text,
      excerpt:(row.body_text||'').slice(0,140),len:(row.body_text||'').length,
      updated:row.updated,url:'',internal:true});
    KB.meta.total=KB.docs.length;
    edMsg('ok','《'+d.title+'》已提交。');
    buildIndex();
    renderCats(); renderFoot();
    setTimeout(()=>{
      closeEditor();
      $('#edTitle').value='';$('#edMd').value='';$('#edKw').value='';
      CUR='all';Q='';$('#q').value='';renderCats();
      render(); openDoc(newId);   // 用确定的 id 打开，避免同名标题匹配错文章
    },700);
  }catch(e){
    edMsg('err','提交失败：'+e.message);
  }finally{ btn.disabled=false; }
}
$('#writeBtn').onclick=requireAuthThenEdit;
$('#loginBtn').onclick=doLogin;
$('#loginPin').addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});
$('#loginMask').addEventListener('click',e=>{if(e.target===$('#loginMask'))$('#loginMask').classList.remove('on');});
$('#edClose').onclick=closeEditor;
$('#editorMask').onclick=closeEditor;
$('#edMd').addEventListener('input',updatePrev);
$('#edTitle').addEventListener('input',updatePrev);
$('#edCat').addEventListener('change',updatePrev);
$('#edSubmit').onclick=submitArticle;

// 搜索框 placeholder：按框宽能放几个关键词就放几个，末尾不做省略号。
// 例：宽屏「搜索 实验设计 / 报告解读 / 广告投放 / 假设检验」，窄屏自动减到「搜索 实验设计 / 报告解读」。
(function(){
  const q=$('#q'); if(!q)return;
  const prefix=q.dataset.phPrefix||'搜索';
  const kws=(q.dataset.phKw||'').split(',').map(s=>s.trim()).filter(Boolean);
  const meas=document.createElement('span');
  meas.style.cssText='position:absolute;visibility:hidden;white-space:nowrap;left:-9999px';
  document.body.appendChild(meas);
  function width(text){
    const cs=getComputedStyle(q);
    meas.style.font=cs.font||`${cs.fontSize} ${cs.fontFamily}`;
    meas.textContent=text; return meas.offsetWidth;
  }
  function pick(){
    const avail=q.clientWidth-92;   // 减去左右图标/内边距
    let n=0;
    for(let k=1;k<=kws.length;k++){
      if(width(prefix+' '+kws.slice(0,k).join(' / '))<=avail) n=k; else break;
    }
    if(n===0) n=1;                  // 至少显示一个，实在放不下就交给输入框自身裁剪
    q.placeholder = prefix+' '+kws.slice(0,n).join(' / ');
  }
  pick();
  if(window.ResizeObserver){ new ResizeObserver(pick).observe(q); }
  else{ window.addEventListener('resize',pick); }
})();

boot();
