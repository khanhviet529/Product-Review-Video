"""
Tạo control_panel.html (mở thẳng bằng trình duyệt, không cần server).

    python tools/build_panel.py

Bảng điều khiển có: danh sách 40 sản phẩm + tiến độ, nút COPY prompt từng clip, ảnh tham chiếu cần tải lên Flow,
nút "Copy clip kế tiếp", ô tích đã tạo / đã tải / đã xóa logo, bộ đếm credit. Trạng thái tích tay được lưu trong trình duyệt;
file thật (raw/, clean/) được tự nhận khi chạy lại lệnh này.
"""
import json
import sys
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CREDITS_PER_CLIP = 12
MONTHLY = 1000


def fences(md: Path):
    return re.findall(r"```\n(.*?)\n```", md.read_text(encoding="utf-8"), re.S)


def collect():
    chars = fences(ROOT / "characters" / "presenters.md")
    f_block, m_block, studio = chars[0].strip(), chars[1].strip(), chars[2].strip()
    img_prompts = []
    for tag, block in (("F", f_block), ("M", m_block)):
        img_prompts.append({
            "name": f"presenter_{tag}_front.png",
            "text": f"Photorealistic portrait, vertical 9:16, {block}, seated at a light oak desk in {studio}, facing the camera, "
                    "hands resting on the desk, neutral soft smile, sharp focus on face, natural skin texture"})
        img_prompts.append({
            "name": f"presenter_{tag}_side.png",
            "text": f"Photorealistic portrait, vertical 9:16, {block}, seated at a light oak desk in {studio}, "
                    "three-quarter view looking slightly to the right, neutral soft smile, sharp focus on face, natural skin texture"})
    products = []
    for pdir in sorted((ROOT / "products").iterdir()):
        if not pdir.is_dir():
            continue
        pid = pdir.name.split("_")[0]
        item = {"id": pid, "slug": pdir.name, "model": pdir.name, "status": "chua_lam", "price": "", "takeaway": "", "clips": [],
                "images": [], "sources": [], "unverified": [], "official": ""}
        rj, pj = pdir / "research.json", pdir / "prompts.json"
        if rj.exists():
            try:
                r = json.loads(rj.read_text(encoding="utf-8"))
                pv = r.get("price_vnd") or {}
                item.update(model=r.get("chosen_model", item["model"]), status=r.get("status", "?"),
                            takeaway=r.get("takeaway", ""), official=r.get("official_page", ""),
                            price=(f"{pv['low']:,}-{pv.get('high', pv['low']):,} đ ({pv.get('as_of', '')})".replace(",", ".") if pv.get("low") else ""),
                            sources=[{"title": s.get("title", s["url"]), "url": s["url"]} for s in r.get("sources", [])],
                            unverified=r.get("unverified", []))
            except Exception:
                pass
        if pj.exists():
            try:
                p = json.loads(pj.read_text(encoding="utf-8"))
                for c in p.get("clips", []):
                    nn = f"C{int(c['n']):02d}"
                    item["clips"].append({
                        "code": c["code"], "n": c["n"], "role": c.get("role", ""), "narration": c.get("narration_vi", ""),
                        "camera": c.get("camera", ""), "reason": c.get("camera_reason", ""),
                        "ref": c.get("ref_images", []), "prompt": c.get("flow_prompt", ""),
                        "raw": (pdir / "raw" / f"{nn}.mp4").exists(), "clean": (pdir / "clean" / f"{nn}.mp4").exists()})
            except Exception:
                pass
        imgdir = pdir / "ref_images"
        if imgdir.exists():
            item["images"] = [f"products/{pdir.name}/ref_images/{f.name}" for f in sorted(imgdir.glob("*.jpg"))]
        products.append(item)
    return {"products": products, "charPrompts": img_prompts, "perClip": CREDITS_PER_CLIP, "monthly": MONTHLY}


HTML = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bảng điều khiển review</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#262b36;--tx:#e8eaf0;--mut:#8b93a7;--ac:#6ea8fe;--ok:#4cc38a;--warn:#f0b429;--bad:#ef6a6a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif;display:flex;height:100vh}
aside{width:320px;border-right:1px solid var(--line);display:flex;flex-direction:column;background:#12151b}
aside .top{padding:12px;border-bottom:1px solid var(--line)}
#list{overflow:auto;flex:1}
.item{padding:9px 12px;border-bottom:1px solid var(--line);cursor:pointer}
.item:hover,.item.sel{background:#1b2030}
.item .nm{font-weight:600}.item small{color:var(--mut)}
.bar{height:5px;background:#222834;border-radius:3px;margin-top:5px;overflow:hidden}.bar i{display:block;height:100%;background:var(--ok)}
main{flex:1;overflow:auto;padding:18px 24px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:22px 0 8px}
.mut{color:var(--mut)}.pill{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--line);font-size:12px;margin-right:4px}
.pill.ok{color:var(--ok);border-color:var(--ok)}.pill.warn{color:var(--warn);border-color:var(--warn)}.pill.bad{color:var(--bad);border-color:var(--bad)}
button{background:#232a3b;color:var(--tx);border:1px solid #33405c;border-radius:6px;padding:6px 12px;cursor:pointer;font:inherit}
button:hover{background:#2c3550}button.pri{background:var(--ac);color:#0b1020;border-color:var(--ac);font-weight:600}
input[type=search]{width:100%;padding:7px 10px;border-radius:6px;border:1px solid var(--line);background:#0e1117;color:var(--tx)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}
.card.done{border-color:#2d5a45}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
textarea{width:100%;min-height:96px;margin-top:8px;background:#0e1117;color:var(--tx);border:1px solid var(--line);border-radius:6px;padding:8px;font:12.5px/1.45 ui-monospace,Consolas,monospace}
.imgs{display:flex;gap:8px;flex-wrap:wrap}.imgs a{display:block}.imgs img{height:120px;border-radius:6px;border:1px solid var(--line);display:block}
.chk label{margin-right:14px;white-space:nowrap}
.stat{display:flex;gap:14px;flex-wrap:wrap}.stat div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px}
.stat b{font-size:18px;display:block}
details{margin:6px 0}summary{cursor:pointer;color:var(--mut)}
.toast{position:fixed;right:18px;bottom:18px;background:var(--ok);color:#06210f;padding:8px 14px;border-radius:8px;opacity:0;transition:.2s;pointer-events:none;font-weight:600}
.toast.on{opacity:1}
a{color:var(--ac)}
</style></head><body>
<aside><div class="top">
<div class="stat"><div><b id="sCredit">0</b><span class="mut">credit đã dùng</span></div><div><b id="sMonth">0</b><span class="mut">tháng ước tính</span></div></div>
<p class="mut" style="margin:8px 0 6px" id="sProg"></p>
<button class="pri" id="btnNext" style="width:100%">Copy clip kế tiếp</button>
<div style="height:8px"></div><input type="search" id="q" placeholder="Tìm sản phẩm...">
<div style="margin-top:8px" class="row"><button id="btnChar">Nhân vật</button><button id="btnExp">Xuất trạng thái</button><button id="btnImp">Nhập</button></div>
</div><div id="list"></div></aside>
<main id="main"></main><div class="toast" id="toast">Đã copy</div>
<script>
const DATA = __DATA__;
const KEY = "review_panel_state_v1";
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch(e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch(e) {} };
const st = (code) => state[code] || (state[code] = {made:false, dl:false, clean:false});
const isMade = (c) => st(c.code).made || c.raw || c.clean;
const isDl = (c) => st(c.code).dl || c.raw || c.clean;
const isClean = (c) => st(c.code).clean || c.clean;
let sel = DATA.products[0]?.id, filter = "", view = "product";
const esc = s => (s||"").replace(/[&<>"]/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
function toast(t){const e=document.getElementById("toast");e.textContent=t||"Đã copy";e.classList.add("on");setTimeout(()=>e.classList.remove("on"),1200)}
async function copy(text){ try{ await navigator.clipboard.writeText(text); }catch(e){ const t=document.createElement("textarea"); t.value=text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); } toast(); }
function prodStats(p){const n=p.clips.length;return {n, made:p.clips.filter(isMade).length, clean:p.clips.filter(isClean).length}}
function renderStats(){
  let made=0,total=0,clean=0; DATA.products.forEach(p=>{const s=prodStats(p);made+=s.made;total+=s.n;clean+=s.clean});
  const credit=made*DATA.perClip; document.getElementById("sCredit").textContent=credit+" / "+(total*DATA.perClip);
  document.getElementById("sMonth").textContent=(total*DATA.perClip/DATA.monthly).toFixed(1);
  document.getElementById("sProg").textContent=`${made}/${total} clip đã tạo · ${clean} đã xóa logo`;
}
function renderList(){
  const L=document.getElementById("list"); L.innerHTML="";
  DATA.products.filter(p=>!filter||(p.model+p.slug).toLowerCase().includes(filter)).forEach(p=>{
    const s=prodStats(p), pct=s.n?Math.round(100*s.made/s.n):0;
    const d=document.createElement("div"); d.className="item"+(p.id===sel&&view==="product"?" sel":"");
    d.innerHTML=`<div class="nm">${p.id}. ${esc(p.model)}</div><small>${s.made}/${s.n} clip · ${esc(p.status)}</small><div class="bar"><i style="width:${pct}%"></i></div>`;
    d.onclick=()=>{sel=p.id;view="product";render()}; L.appendChild(d);
  });
}
function statusPill(s){const c=s==="xac_minh"?"ok":s==="mot_phan"?"warn":"bad";return `<span class="pill ${c}">${esc(s)}</span>`}
function renderProduct(){
  const p=DATA.products.find(x=>x.id===sel); if(!p) return "";
  const imgs=p.images.length?`<div class="imgs">${p.images.map(u=>`<a href="${u}" target="_blank"><img src="${u}" title="${u.split('/').pop()}"></a>`).join("")}</div><p class="mut">Ảnh nằm trong <code>products/${p.slug}/ref_images/</code>. Tải lên Flow: <b>product_main.jpg</b> (+ ảnh góc nghiêng nếu cần).</p>`:`<p class="mut">Chưa có ảnh. Chạy <code>python tools/find_images.py ${p.id}</code>.</p>`;
  const src=p.sources.map(s=>`<li><a href="${s.url}" target="_blank">${esc(s.title)}</a></li>`).join("");
  let h=`<h1>${p.id}. ${esc(p.model)}</h1><div>${statusPill(p.status)}<span class="pill">${esc(p.price||"chưa có giá")}</span>${p.official?`<a href="${p.official}" target="_blank">trang chính hãng</a>`:""}</div>
  <p><b>Câu mang về:</b> ${esc(p.takeaway)||"<span class=mut>chưa có</span>"}</p>
  <h2>Ảnh tham chiếu</h2>${imgs}
  <details><summary>Nguồn (${p.sources.length})${p.unverified.length?` · chưa xác minh (${p.unverified.length})`:""}</summary><ul>${src}</ul>${p.unverified.length?`<p class="mut">Chưa xác minh: ${p.unverified.map(esc).join(" · ")}</p>`:""}</details>
  <h2>Clip (${p.clips.length}) · ${p.clips.length*DATA.perClip} credit</h2>`;
  p.clips.forEach(c=>{
    const s=st(c.code), done=isClean(c);
    h+=`<div class="card ${done?"done":""}"><div class="row"><b>${c.code}</b><span class="pill">${esc(c.role)}</span><span class="mut">${esc(c.camera)}${c.reason?" · "+esc(c.reason):""}</span></div>
    <p style="margin:6px 0">${esc(c.narration)}</p>
    <div class="row"><button class="pri" onclick="doCopy('${c.code}')">Copy prompt</button><span class="mut">ảnh tải lên: ${c.ref.map(esc).join(", ")||"—"}</span></div>
    <div class="chk row" style="margin-top:8px"><label><input type="checkbox" ${isMade(c)?"checked":""} ${c.raw||c.clean?"disabled":""} onchange="setS('${c.code}','made',this.checked)"> đã tạo trên Flow</label>
    <label><input type="checkbox" ${isDl(c)?"checked":""} ${c.raw||c.clean?"disabled":""} onchange="setS('${c.code}','dl',this.checked)"> đã tải về${c.raw?" (có file raw)":""}</label>
    <label><input type="checkbox" ${isClean(c)?"checked":""} ${c.clean?"disabled":""} onchange="setS('${c.code}','clean',this.checked)"> đã xóa logo${c.clean?" (có file clean)":""}</label></div>
    <details><summary>Xem prompt</summary><textarea readonly onclick="this.select()">${esc(c.prompt)}</textarea></details></div>`;
  });
  return h;
}
function renderChars(){
  let h=`<h1>Nhân vật dẫn</h1><p class="mut">Tạo 1 lần bằng công cụ tạo ảnh của Flow, lưu vào <code>characters/</code>. Khi tạo clip có người dẫn, tải <b>ảnh front</b> lên cùng ảnh sản phẩm. Sản phẩm số lẻ: người dẫn F; số chẵn: M.</p>`;
  DATA.charPrompts.forEach((c,i)=>{h+=`<div class="card"><b>${c.name}</b><div class="row" style="margin-top:6px"><button class="pri" onclick="copyChar(${i})">Copy prompt</button></div><textarea readonly onclick="this.select()">${esc(c.text)}</textarea></div>`});
  return h;
}
function render(){renderStats();renderList();document.getElementById("main").innerHTML=view==="char"?renderChars():renderProduct()}
function setS(code,k,v){st(code)[k]=v;save();render()}
function doCopy(code){const c=DATA.products.flatMap(p=>p.clips).find(x=>x.code===code);copy(c.prompt)}
function copyChar(i){copy(DATA.charPrompts[i].text)}
document.getElementById("q").oninput=e=>{filter=e.target.value.toLowerCase();renderList()};
document.getElementById("btnChar").onclick=()=>{view=view==="char"?"product":"char";render()};
document.getElementById("btnNext").onclick=()=>{
  for(const p of DATA.products){for(const c of p.clips){if(!isMade(c)){sel=p.id;view="product";copy(c.prompt);toast("Đã copy "+c.code+" — dán vào Flow, tạo xong thì tích 'đã tạo'");render();return}}}
  toast("Hết clip cần tạo");
};
document.getElementById("btnExp").onclick=()=>copy(JSON.stringify(state));
document.getElementById("btnImp").onclick=()=>{const t=prompt("Dán JSON trạng thái:");if(t){try{state=JSON.parse(t);save();render()}catch(e){alert("JSON không hợp lệ")}}};
render();
</script></body></html>
"""


def main():
    data = collect()
    out = ROOT / "control_panel.html"
    out.write_text(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    n = sum(len(p["clips"]) for p in data["products"])
    print(f"Da tao {out}  ({len(data['products'])} san pham, {n} clip, {n * CREDITS_PER_CLIP} credit)")


if __name__ == "__main__":
    main()
