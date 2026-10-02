import { useEffect, useMemo, useState } from "react";
import type { Block, PaperDocument, Sample, Section } from "./contracts";
import { PdfPreview } from "./PdfPreview";
import "./styles.css";

function flatten(sections: Section[]): Section[] { return sections.flatMap(s => [s, ...flatten(s.children)]); }
async function getJson<T>(url:string, signal:AbortSignal):Promise<T> {
  const response = await fetch(url, {signal});
  if (!response.ok) throw new Error(`请求失败 (${response.status})`);
  return response.json();
}
export default function App() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [sampleId, setSampleId] = useState("");
  const [doc, setDoc] = useState<PaperDocument|null>(null);
  const [active, setActive] = useState<string|null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    getJson<Sample[]>("/api/samples",controller.signal).then(value => {
      setSamples(value); setSampleId(value.find(s=>s.id==="transformer")?.id ?? value[0]?.id ?? "");
    }).catch(() => { if (!controller.signal.aborted) setError("无法连接后端。请检查 8000 端口服务后重试。"); })
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    setDoc(null); setActive(null); setPage(1);
    if (!sampleId) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    getJson<PaperDocument>(`/api/samples/${sampleId}/document`,controller.signal).then(setDoc)
      .catch(()=>{if(!controller.signal.aborted)setError("结构化样本读取失败。请重新导出样本后重试。");})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  }, [sampleId, attempt]);
  const sections = useMemo(()=>doc?flatten(doc.sections):[],[doc]);
  const blocks = useMemo(()=>doc?.blocks.filter(b=>b.page===page)??[],[doc,page]);
  const sample = samples.find(s=>s.id===sampleId);
  const select = (block:Block) => { setPage(block.page); setActive(block.id); };
  useEffect(() => { if(active) document.getElementById(active)?.scrollIntoView({block:"nearest"}); },[active,page]);
  return <div className="app">
    <header><strong>Paperx<span className="logo-dot">.</span></strong><span>RESEARCH WORKSPACE <i>/</i> 工程验证</span>
      <select aria-label="选择样本" value={sampleId} onChange={e=>setSampleId(e.target.value)}>
        <option value="" disabled>选择测试论文</option>
        {samples.map(s=><option key={s.id} value={s.id}>{s.paper.title}{s.synthetic?" · 合成样本":""}</option>)}
      </select><b className="stage">阶段 0</b>
    </header>
    {error && <div role="alert" className="error">{error}<button onClick={()=>setAttempt(a=>a+1)}>重试</button></div>}
    {!doc ? <main className="empty"><div className="eyebrow">PDF → STRUCTURED PAPER</div><h1>{loading?"正在载入本地论文…":"从结构化论文开始"}</h1>
      <p>阶段 0 只验证真实 PDF、结构化数据和坐标，不提供翻译、上传或公式识别。</p>
      {!loading&&!error&&<p>还没有样本。请运行 <code>.venv/Scripts/python.exe scripts/prepare_samples.py</code></p>}
    </main> : <main className="workspace">
      <aside className="outline"><div className="eyebrow">DOCUMENT OUTLINE</div><h2>论文目录 <span>{sections.length}</span></h2>
        {!sections.length&&<p className="muted">未识别出可靠目录，请按页检查原文。</p>}
        {sections.map(s=><button className={`toc ${active===s.block_id?"current":""}`} style={{paddingLeft:`${10+(s.level-1)*10}px`}} key={s.id}
          onClick={()=>{const b=doc.blocks.find(b=>b.id===s.block_id);if(b)select(b);}}>{s.title}</button>)}
        <div className="outline-note">自动提取 · 待人工复核<br/>不是完整阅读器</div>
      </aside>
      <section className="lab">
        <div className="title-row"><div><div className="eyebrow">{sample?.synthetic?"SYNTHETIC TEST FIXTURE":"LOCAL PAPER / NLP"}</div>
          <h1>{sample?.paper.title}</h1><p className="subtitle">{doc.pages.length} 页 <span>·</span> {doc.blocks.length} 个结构块 <span>·</span> 原始 PDF 保留</p></div>
          <a className="pdf-link" href={`/api/samples/${sampleId}/pdf`} target="_blank" rel="noreferrer">原 PDF ↗</a>
        </div>
        <div className="notice"><b>可行性验证</b><span>右侧为提取的原文，不是中文译文。公式未经人工核验，暂不允许复制。</span></div>
        <div className="lab-toolbar"><span className="live-dot"/>本地解析数据<span className="spacer"/>
          <button aria-label="上一页" disabled={page<=1} onClick={()=>{setPage(p=>p-1);setActive(null);}}>←</button>
          <label>页码 <select aria-label="页码" value={page} onChange={e=>{setPage(Number(e.target.value));setActive(null);}}>
            {doc.pages.map(p=><option key={p.number} value={p.number}>{p.number}</option>)}</select> / {doc.pages.length}</label>
          <button aria-label="下一页" disabled={page>=doc.pages.length} onClick={()=>{setPage(p=>p+1);setActive(null);}}>→</button>
        </div>
        <div className="panels">
          <section className="panel"><div className="panel-label"><b>原文 PDF</b><span>点击区域检查坐标</span></div>
            <div className="pdf-scroll"><PdfPreview key={sampleId} url={`/api/samples/${sampleId}/pdf`} page={page} doc={doc} active={active} onSelect={select}/></div>
          </section>
          <section className="panel"><div className="panel-label"><b>结构化原文</b><span>第 {page} 页 · {blocks.length} 块</span></div>
            <div className="blocks-scroll">
              {!blocks.length&&<div className="block-empty"><h2>此页没有可提取的文本层</h2><p>OCR 尚未实现。左侧原 PDF 仍可查看。</p></div>}
              {blocks.map(b=><article id={b.id} className={`block ${active===b.id?"active":""}`} key={b.id}>
                <div className="meta"><button onClick={()=>select(b)} aria-label={`定位块 ${b.id}`}>{b.type}</button><span>p.{b.page}</span></div>
                {b.type==="heading"?<h2>{b.text}</h2>:<p>{b.text}</p>}
                <code className="block-id">{b.id}</code>
                {b.formula&&<div className="formula-warning">{b.formula.latex ? 'LaTeX 待核验' : 'LaTeX 未识别'} · 需要人工校正</div>}
                {active===b.id&&<div className="coords">bbox: {Object.values(b.bbox).map(v=>v.toFixed(3)).join(" / ")}</div>}
              </article>)}
            </div>
          </section>
        </div>
      </section>
      <div className="symmetry" aria-hidden="true"/>
    </main>}
    <footer><span><b className="live-dot"/> LOCAL ONLY · 未调用外部 AI</span><span>归一化坐标 / 未旋转 MediaBox / 左上原点</span><span>0.1 · 工程基线</span></footer>
  </div>;
}
