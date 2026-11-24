# -*- coding: utf-8 -*-
"""后台数据浏览：人类可读的 Web 页面 + 配套只读 API。
访问 http://localhost:8000/admin
"""
import os
import sys
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from common import load_config, ROOT

router = APIRouter()
_cfg = load_config()
DB_PATH = os.path.join(ROOT, _cfg.get("storage", {}).get("db_path", "data/listings.db"))


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _row(r):
    d = dict(r)
    try:
        d["score_reasons"] = json.loads(d.get("score_reasons") or "[]")
    except Exception:
        d["score_reasons"] = []
    try:
        d["score_detail"] = json.loads(d.get("score_detail") or "{}")
    except Exception:
        d["score_detail"] = {}
    for k in ("second_listing", "has_defect_note"):
        d[k] = bool(d.get(k))
    return d


@router.get("/api/admin/overview")
def admin_overview():
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    by_source = [dict(r) for r in c.execute(
        "SELECT source, COUNT(*) n FROM listings GROUP BY source ORDER BY n DESC"
    )]
    by_category = [dict(r) for r in c.execute(
        "SELECT category, COUNT(*) n FROM listings GROUP BY category ORDER BY category"
    )]
    score_ranges = [dict(r) for r in c.execute("""
        SELECT CASE
          WHEN score >= 80 THEN '80+'
          WHEN score >= 60 THEN '60-79'
          WHEN score >= 40 THEN '40-59'
          ELSE '<40'
        END AS bucket, COUNT(*) n FROM listings GROUP BY bucket ORDER BY bucket DESC
    """)]
    changes = c.execute("SELECT COUNT(*) FROM listing_changes").fetchone()[0]
    latest = c.execute("SELECT MAX(date) FROM recommendations").fetchone()[0] or ""
    rec_count = c.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    v2 = c.execute("SELECT COUNT(*) FROM listings WHERE scoring_version='v2'").fetchone()[0]
    avg = c.execute("SELECT ROUND(AVG(score),1) FROM listings").fetchone()[0] or 0
    c.close()
    return {
        "total": total,
        "by_source": by_source,
        "by_category": by_category,
        "score_ranges": score_ranges,
        "changes": changes,
        "latest_date": latest,
        "recommendations": rec_count,
        "v2_count": v2,
        "avg_score": avg,
    }


@router.get("/api/admin/listings")
def admin_listings(
    search: str = Query(default=""),
    source: str = Query(default=""),
    category: str = Query(default=""),
    min_score: int = Query(default=0, ge=0, le=100),
    sort: str = Query(default="score"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    where, args = ["1=1"], []
    if search:
        where.append("(title LIKE ? OR seller LIKE ? OR id LIKE ?)")
        kw = f"%{search}%"
        args += [kw, kw, kw]
    if source:
        where.append("source=?"); args.append(source)
    if category:
        where.append("category=?"); args.append(category)
    if min_score:
        where.append("score>=?"); args.append(min_score)
    w = " AND ".join(where)
    order = {
        "score": "score DESC, collected_at DESC",
        "value": "value_score DESC",
        "risk": "risk_score DESC",
        "title": "title_score DESC",
        "price_asc": "price_yuan ASC",
        "price_desc": "price_yuan DESC",
        "newest": "collected_at DESC",
    }.get(sort, "score DESC")
    c = _conn()
    total = c.execute(f"SELECT COUNT(*) FROM listings WHERE {w}", args).fetchone()[0]
    rows = c.execute(
        f"SELECT * FROM listings WHERE {w} ORDER BY {order} LIMIT ? OFFSET ?",
        args + [page_size, (page - 1) * page_size],
    ).fetchall()
    c.close()
    return {"items": [_row(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/api/admin/listings/{listing_id}")
def admin_listing_detail(listing_id: str):
    c = _conn()
    r = c.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    c.close()
    if not r:
        return {"error": "not found"}
    return _row(r)


@router.get("/api/admin/recommendations")
def admin_recommendations(
    date: str = Query(default=""),
    category: str = Query(default=""),
):
    c = _conn()
    if not date:
        date = c.execute("SELECT MAX(date) FROM recommendations").fetchone()[0] or ""
    w, args = ["r.date=?"], [date]
    if category:
        w.append("r.category=?"); args.append(category)
    rows = c.execute(f"""
        SELECT l.*, r.rank, r.date AS rec_date FROM recommendations r
        JOIN listings l ON l.id=r.listing_id
        WHERE {' AND '.join(w)} ORDER BY r.category, r.rank
    """, args).fetchall()
    dates = [r[0] for r in c.execute("SELECT DISTINCT date FROM recommendations ORDER BY date DESC LIMIT 15")]
    c.close()
    return {"date": date, "dates": dates, "items": [_row(r) for r in rows]}


@router.get("/api/admin/changes")
def admin_changes(limit: int = Query(default=100, ge=1, le=1000)):
    c = _conn()
    rows = c.execute("""
        SELECT c.*, l.title, l.url, l.category FROM listing_changes c
        LEFT JOIN listings l ON l.id=c.listing_id
        ORDER BY c.changed_at DESC LIMIT ?
    """, (limit,)).fetchall()
    c.close()
    return {"items": [dict(r) for r in rows]}


ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>闲置资源优选 · 数据后台</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--text:#1f2329;--muted:#646a73;--border:#e5e6eb;--primary:#3370ff;--ok:#00b42a;--warn:#ff7d00;--danger:#f53f3f}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}
.wrap{max-width:1400px;margin:0 auto;padding:24px}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
h1{font-size:22px;font-weight:600}
.sub{color:var(--muted);font-size:13px;margin-top:4px}
button{cursor:pointer;font-family:inherit;font-size:14px;border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:6px;padding:7px 14px;transition:.15s}
button:hover{border-color:var(--primary);color:var(--primary)}
button.primary{background:var(--primary);color:#fff;border-color:var(--primary)}
button.primary:hover{opacity:.9}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
.stat .label{color:var(--muted);font-size:13px}
.stat .value{font-size:26px;font-weight:600;margin-top:6px}
.stat .hint{color:var(--muted);font-size:12px;margin-top:4px}
.tabs{display:flex;gap:6px;margin-bottom:16px;border-bottom:1px solid var(--border)}
.tabs button{border:none;border-bottom:2px solid transparent;border-radius:0;background:transparent;padding:10px 18px;color:var(--muted)}
.tabs button.active{color:var(--primary);border-bottom-color:var(--primary);font-weight:500}
.panel{display:none}
.panel.active{display:block}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;margin-bottom:16px}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
.filters input,.filters select{border:1px solid var(--border);border-radius:6px;padding:7px 10px;font-size:14px;font-family:inherit;background:var(--card);color:var(--text)}
.filters input:focus,.filters select:focus{outline:none;border-color:var(--primary)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:top}
th{background:#fafafa;color:var(--muted);font-weight:500;white-space:nowrap;position:sticky;top:0}
tr:hover td{background:#f7f9ff}
.limit{max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;white-space:nowrap}
.tag-b{background:#fff3e8;color:#d46b08}
.tag-c{background:#e6f4ff;color:#0958d9}
.score{font-weight:600}
.score.high{color:var(--ok)}
.score.mid{color:var(--warn)}
.score.low{color:var(--muted)}
.money{color:var(--danger);font-weight:500;white-space:nowrap}
.muted{color:var(--muted)}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}
.pager{display:flex;justify-content:space-between;align-items:center;margin-top:14px;color:var(--muted);font-size:13px}
.pager .btns{display:flex;gap:8px}
.bar{height:8px;border-radius:4px;background:var(--primary);min-width:2px;display:inline-block;vertical-align:middle}
.dist-row{display:flex;align-items:center;gap:10px;margin:8px 0}
.dist-row .name{width:90px;color:var(--muted)}
.dist-row .num{width:50px;text-align:right;font-variant-numeric:tabular-nums}
.empty{text-align:center;padding:48px;color:var(--muted)}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-box{background:var(--card);border-radius:12px;width:min(760px,100%);max-height:86vh;overflow:auto;padding:24px}
.modal-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.modal-head h2{font-size:17px;font-weight:600}
.kv{display:grid;grid-template-columns:120px 1fr;gap:10px 16px;font-size:13px;margin-bottom:18px}
.kv .k{color:var(--muted)}
.kv .v{word-break:break-word}
.reasons{display:flex;flex-wrap:wrap;gap:6px}
.reason{background:#f0f5ff;color:#1d39c4;padding:3px 9px;border-radius:12px;font-size:12px}
.dims{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:18px}
.dim{text-align:center;background:var(--bg);border-radius:8px;padding:10px 6px}
.dim .n{font-size:11px;color:var(--muted)}
.dim .v{font-size:20px;font-weight:600;margin:4px 0}
.dim .track{height:5px;border-radius:3px;background:var(--border);overflow:hidden}
.dim .fill{height:100%;border-radius:3px}
@media(max-width:600px){.dims{grid-template-columns:repeat(3,1fr)}}
@media(max-width:800px){.wrap{padding:12px}.kv{grid-template-columns:90px 1fr}table{font-size:12px}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div><h1>闲置资源优选 · 数据后台</h1><div class="sub">公开采集数据的人类可读视图 · 只读，不影响 App 接口</div></div>
  <button onclick="loadAll()">刷新数据</button>
</header>
<div class="stats" id="stats"></div>
<div class="tabs">
  <button class="active" data-tab="overview" onclick="switchTab('overview')">总览</button>
  <button data-tab="listings" onclick="switchTab('listings')">标的库</button>
  <button data-tab="recommend" onclick="switchTab('recommend')">每日优选</button>
  <button data-tab="changes" onclick="switchTab('changes')">变更记录</button>
</div>

<section class="panel active" id="panel-overview">
  <div class="card"><h3>数据来源分布</h3><div id="dist-source"></div></div>
  <div class="card"><h3>评分分布</h3><div id="dist-score"></div></div>
</section>

<section class="panel" id="panel-listings">
  <div class="card">
    <div class="filters">
      <input id="f-search" placeholder="搜索标题 / 卖方 / ID" onkeydown="if(event.key==='Enter')loadListings(1)">
      <select id="f-source" onchange="loadListings(1)"><option value="">全部来源</option></select>
      <select id="f-category" onchange="loadListings(1)"><option value="">全部分类</option><option value="B">企业类 B</option><option value="C">个人类 C</option></select>
      <select id="f-score" onchange="loadListings(1)"><option value="0">全部评分</option><option value="60">≥60</option><option value="70">≥70</option><option value="80">≥80</option></select>
      <select id="f-sort" onchange="loadListings(1)"><option value="score">按综合分</option><option value="value">按性价比分</option><option value="risk">按安全分</option><option value="title">按权属分</option><option value="newest">按采集时间</option><option value="price_asc">价格从低到高</option><option value="price_desc">价格从高到低</option></select>
      <button class="primary" onclick="loadListings(1)">查询</button>
    </div>
    <table><thead><tr><th>综合</th><th>性价比</th><th>安全</th><th>分类</th><th>标题</th><th>类型</th><th>价格</th><th>截止</th><th>操作</th></tr></thead><tbody id="tb-listings"></tbody></table>
    <div class="pager"><span id="pg-info"></span><div class="btns"><button onclick="loadListings(page-1)" id="pg-prev">上一页</button><button onclick="loadListings(page+1)" id="pg-next">下一页</button></div></div>
  </div>
</section>

<section class="panel" id="panel-recommend">
  <div class="card">
    <div class="filters">
      <select id="r-date" onchange="loadRecommend()"></select>
      <select id="r-category" onchange="loadRecommend()"><option value="">B + C 全部</option><option value="B">企业类 B</option><option value="C">个人类 C</option></select>
    </div>
    <table><thead><tr><th>#</th><th>分类</th><th>评分</th><th>标题</th><th>价格</th><th>理由</th><th>操作</th></tr></thead><tbody id="tb-recommend"></tbody></table>
  </div>
</section>

<section class="panel" id="panel-changes">
  <div class="card">
    <div class="filters"><span class="muted">最近变更（最多 100 条）</span><button onclick="loadChanges()">刷新</button></div>
    <table><thead><tr><th>时间</th><th>标的</th><th>字段</th><th>原值</th><th>新值</th></tr></thead><tbody id="tb-changes"></tbody></table>
  </div>
</section>
</div>

<div class="modal" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal-box">
    <div class="modal-head"><h2 id="m-title">详情</h2><button onclick="closeModal()">关闭</button></div>
    <div class="dims" id="m-dims"></div>
    <div class="kv" id="m-kv"></div>
    <h3>评分理由</h3><div class="reasons" id="m-reasons"></div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
let page = 1, totalPages = 1, cache = {};
async function api(p){ const r = await fetch(p); if(!r.ok) throw new Error(r.status); return r.json(); }
function esc(s){ return String(s??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function money(n){ if(n==null||n==='') return '<span class="muted">—</span>'; const v=Number(n); if(!isFinite(v))return esc(n); return '¥'+v.toLocaleString('zh-CN',{maximumFractionDigits:0}); }
function date(s){ return s ? String(s).slice(0,16).replace('T',' ') : '<span class="muted">—</span>'; }
function cut(s,n=46){ s=String(s??''); return s.length>n ? '<span title="'+esc(s)+'">'+esc(s.slice(0,n))+'…</span>' : esc(s); }
function catTag(c){ return c==='B' ? '<span class="tag tag-b">企业 B</span>' : (c==='C' ? '<span class="tag tag-c">个人 C</span>' : '<span class="muted">—</span>'); }
function scoreHtml(s){ const n=Number(s)||0; const cls=n>=80?'high':(n>=60?'mid':'low'); return '<span class="score '+cls+'">'+n+'</span>'; }
function switchTab(t){ document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===t)); document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id==='panel-'+t)); }
function loadAll(){ loadOverview(); loadListings(1); loadRecommend(); loadChanges(); }

async function loadOverview(){
  try{
    const d = await api('/api/admin/overview'); cache.overview = d;
    $('stats').innerHTML = [
      ['标的总数', d.total, '来自 '+d.by_source.length+' 个平台'],
      ['企业类 B', (d.by_category.find(x=>x.category==='B')||{}).n||0, '大额资产'],
      ['个人类 C', (d.by_category.find(x=>x.category==='C')||{}).n||0, '房产 / 资产'],
      ['变更记录', d.changes, '价格 / 状态变动'],
      ['平均评分', d.avg_score, 'v2 评分 '+d.v2_count+' 条'],
      ['最近优选', d.latest_date||'—', d.recommendations+' 条推荐'],
    ].map(x=>'<div class="stat"><div class="label">'+x[0]+'</div><div class="value">'+x[1]+'</div><div class="hint">'+esc(x[2])+'</div></div>').join('');
    const maxS = Math.max(1,...d.by_source.map(x=>x.n));
    $('dist-source').innerHTML = d.by_source.map(x=>'<div class="dist-row"><span class="name">'+esc(x.source)+'</span><span class="bar" style="width:'+(x.n/maxS*300)+'px"></span><span class="num">'+x.n+'</span></div>').join('') || '<div class="empty">暂无数据</div>';
    const order=['80+','60-79','40-59','<40'];
    $('dist-score').innerHTML = order.map(k=>{const x=d.score_ranges.find(y=>y.bucket===k);const n=x?x.n:0;return '<div class="dist-row"><span class="name">'+k+' 分</span><span class="bar" style="width:'+(n/Math.max(1,d.total)*300)+'px"></span><span class="num">'+n+'</span></div>';}).join('');
  }catch(e){ $('stats').innerHTML='<div class="empty">加载失败：'+esc(e.message)+'</div>'; }
}

async function loadListings(p){
  page = Math.max(1, p||1);
  const q = new URLSearchParams({search:$('f-search').value,source:$('f-source').value,category:$('f-category').value,min_score:$('f-score').value,sort:$('f-sort').value,page:page,page_size:20});
  try{
    const d = await api('/api/admin/listings?'+q);
    totalPages = Math.max(1, Math.ceil(d.total/d.page_size));
    if($('f-source').options.length===1){ d.items.forEach(()=>{}); }
    $('tb-listings').innerHTML = d.items.map(x=>'<tr>'+
      '<td>'+scoreHtml(x.score)+'</td><td>'+scoreHtml(x.value_score)+'</td><td>'+scoreHtml(x.risk_score)+'</td>'+
      '<td>'+catTag(x.category)+'</td>'+
      '<td class="limit">'+cut(x.title)+'</td><td>'+esc(x.asset_type||'—')+'</td>'+
      '<td class="money">'+money(x.price_yuan)+'</td><td>'+date(x.deadline)+'</td>'+
      '<td><button onclick="showDetail(\''+esc(x.id)+'\')">详情</button>'+(x.url?' <a href="'+esc(x.url)+'" target="_blank" rel="noopener">原页</a>':'')+'</td></tr>').join('') || '<tr><td colspan="9" class="empty">没有符合条件的记录</td></tr>';
    $('pg-info').textContent = '第 '+page+' / '+totalPages+' 页 · 共 '+d.total+' 条';
    $('pg-prev').disabled = page<=1; $('pg-next').disabled = page>=totalPages;
  }catch(e){ $('tb-listings').innerHTML='<tr><td colspan="9" class="empty">加载失败</td></tr>'; }
}

async function loadRecommend(){
  const q = new URLSearchParams({date:$('r-date').value,category:$('r-category').value});
  try{
    const d = await api('/api/admin/recommendations?'+q);
    if($('r-date').options.length===1){ d.dates.forEach(x=>{const o=document.createElement('option');o.value=x;o.textContent=x;$('r-date').appendChild(o);}); $('r-date').value=d.date; }
    $('tb-recommend').innerHTML = d.items.map(x=>'<tr><td>'+x.rank+'</td><td>'+catTag(x.category)+'</td><td>'+scoreHtml(x.score)+'</td>'+
      '<td class="limit">'+cut(x.title)+'</td><td class="money">'+money(x.price_yuan)+'</td>'+
      '<td class="limit">'+esc((x.score_reasons||[]).slice(0,3).join('、'))+'</td>'+
      '<td><button onclick="showDetail(\''+esc(x.id)+'\')">详情</button></td></tr>').join('') || '<tr><td colspan="7" class="empty">该日期暂无推荐</td></tr>';
  }catch(e){ $('tb-recommend').innerHTML='<tr><td colspan="7" class="empty">加载失败</td></tr>'; }
}

async function loadChanges(){
  try{
    const d = await api('/api/admin/changes?limit=100');
    $('tb-changes').innerHTML = d.items.map(x=>'<tr><td>'+date(x.changed_at)+'</td><td class="limit">'+cut(x.title)+'</td><td>'+esc(x.field)+'</td><td>'+cut(String(x.old??'—'),30)+'</td><td>'+cut(String(x.new??'—'),30)+'</td></tr>').join('') || '<tr><td colspan="5" class="empty">暂无变更</td></tr>';
  }catch(e){ $('tb-changes').innerHTML='<tr><td colspan="5" class="empty">加载失败</td></tr>'; }
}

async function showDetail(id){
  let x; try{ x = await api('/api/admin/listings/'+encodeURIComponent(id)); }catch(e){ alert('详情加载失败'); return; }
  if(x.error){ alert('未找到该记录'); return; }
  $('m-title').textContent = x.title||'（无标题）';
  const dimNames = {value:'性价比',title:'权属',risk:'安全',seller:'挂牌方',time:'时效'};
  const detail = x.score_detail || {value:x.value_score,title:x.title_score,risk:x.risk_score,seller:x.seller_score,time:x.time_score};
  $('m-dims').innerHTML = ['value','title','risk','seller','time'].map(k=>{
    const v = Number(detail[k]||0); const cls=v>=75?'high':(v>=55?'mid':'low');
    const color = v>=75?'var(--ok)':(v>=55?'var(--warn)':'var(--danger)');
    return '<div class="dim"><div class="n">'+(dimNames[k]||k)+'</div><div class="v '+cls+'">'+v+'</div><div class="track"><div class="fill" style="width:'+v+'%;background:'+color+'"></div></div></div>';
  }).join('') + '<div class="dim" style="grid-column:span 5;background:#e6f4ff"><div class="n">综合评分</div><div class="v high">'+x.score+'</div><div class="n">市场基准：'+esc(x.market_basis||'—')+'</div></div>';
  const fields = [['ID',x.id],['来源',x.source],['分类',x.category==='B'?'企业类 B':'个人类 C'],['资产类型',x.asset_type],['地区',[x.province,x.city,x.district].filter(Boolean).join(' / ')],['面积',x.area_sqm?x.area_sqm+' ㎡':'—'],['挂牌价',x.price_yuan?money(x.price_yuan):'—'],['价格原文',x.price_text],['评估价',x.appraisal_yuan?money(x.appraisal_yuan):'—'],['折扣率',x.discount_rate?x.discount_rate:'—'],['单价',x.unit_price?x.unit_price+' 元/㎡':'—'],['截止时间',x.deadline],['转让方',x.seller],['转让方等级',x.seller_grade],['二次挂牌',x.second_listing?'是':'否'],['瑕疵说明',x.has_defect_note?'有':'无'],['用途',x.use_type],['发布时间',x.published_at],['采集时间',x.collected_at],['评分版本',x.scoring_version||'v1'],['原页',x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener">打开链接</a>':'—']];
  $('m-kv').innerHTML = fields.map(f=>'<div class="k">'+f[0]+'</div><div class="v">'+(f[1]||'—')+'</div>').join('');
  $('m-reasons').innerHTML = (x.score_reasons||[]).map(r=>'<span class="reason">'+esc(r)+'</span>').join('') || '<span class="muted">无</span>';
  $('modal').classList.add('show');
}
function closeModal(){ $('modal').classList.remove('show'); }

async function bootstrap(){
  try{ const d=await api('/api/admin/overview'); d.by_source.forEach(s=>{const o=document.createElement('option');o.value=s.source;o.textContent=s.source+' ('+s.n+')';$('f-source').appendChild(o);}); }catch(e){}
  loadAll();
}
bootstrap();
</script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_HTML
