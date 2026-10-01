import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Block, PaperDocument } from "./contracts";
import { rotateBBox } from "./coordinates";
GlobalWorkerOptions.workerSrc = workerUrl;

export function PdfPreview({ url, page, doc, active, onSelect }: {
  url: string; page:number; doc:PaperDocument; active:string|null; onSelect:(b:Block)=>void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy|null>(null);
  const [width, setWidth] = useState(600);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [cropSafe, setCropSafe] = useState(true);
  const metadata = doc.pages[page-1];
  useEffect(() => {
    const task = getDocument({url, cMapUrl:"/pdfjs/cmaps/", cMapPacked:true, standardFontDataUrl:"/pdfjs/standard_fonts/", wasmUrl:"/pdfjs/wasm/", iccUrl:"/pdfjs/iccs/"});
    let cancelled = false;
    setPdf(null); setReady(false); setError("");
    task.promise.then(value => { if (!cancelled) setPdf(value); })
      .catch(() => { if (!cancelled) setError("原 PDF 加载失败；结构化数据仍可查看。"); });
    return () => { cancelled = true; void task.destroy(); };
  }, [url]);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!pdf || !metadata) return;
    let cancelled = false;
    let render: RenderTask | undefined;
    setReady(false); setError("");
    void pdf.getPage(page).then(async pdfPage => {
      if (cancelled || !canvas.current) return;
      // PDF.js defaults to CropBox; don't draw misleading MediaBox overlays on cropped pages.
      const view = pdfPage.view;
      setCropSafe(Math.abs((view[2]-view[0])-metadata.width) < 1 &&
        Math.abs((view[3]-view[1])-metadata.height) < 1);
      const base = pdfPage.getViewport({scale:1});
      const viewport = pdfPage.getViewport({scale:Math.max(1,width)/base.width});
      const target = canvas.current;
      const ratio = window.devicePixelRatio || 1;
      target.width = Math.ceil(viewport.width*ratio);
      target.height = Math.ceil(viewport.height*ratio);
      render = pdfPage.render({canvas:target, viewport, transform:[ratio,0,0,ratio,0,0]});
      await render.promise;
      if (!cancelled) setReady(true);
    }).catch(() => { if (!cancelled) setError("这一页无法渲染，请打开原 PDF 检查。"); });
    return () => { cancelled = true; render?.cancel(); };
  }, [pdf, page, width, metadata]);
  return <div ref={host} className="pdf-host">
    {error && <p role="alert" className="notice">{error}</p>}
    {!ready && !error && <p className="pdf-loading">正在渲染第 {page} 页…</p>}
    {!cropSafe && <p className="notice">此页存在裁剪差异：坐标覆盖层已关闭。</p>}
    <div className="pdf-sheet" data-rendered={ready}>
      <canvas ref={canvas} aria-label={`原始 PDF 第 ${page} 页`} />
      {ready && cropSafe && doc.blocks.filter(b=>b.page===page).map(b => {
        const box=rotateBBox(b.bbox, metadata.rotation);
        return <button key={b.id} type="button" title={`${b.type}: ${b.text.slice(0,80)}`}
          aria-label={`查看块 ${b.id}`} onClick={()=>onSelect(b)}
          className={`bbox ${active===b.id?"selected":""}`}
          style={{left:`${box.x*100}%`,top:`${box.y*100}%`,width:`${box.width*100}%`,height:`${box.height*100}%`}} />;
      })}
    </div>
  </div>;
}

