export type BBox = { x:number; y:number; width:number; height:number };
export type Block = {
  id:string; type:string; page:number; order:number; bbox:BBox; text:string;
  heading_level?:number; warnings:string[];
  formula?: {latex:string|null; status:string; confidence:number; source:string; verified_by:string|null} | null;
};
export type Section = { id:string; title:string; block_id:string; level:number; children:Section[] };
export type PaperDocument = {
  paper_id:string; source_sha256:string; parser_version:string;
  pages:{number:number;width:number;height:number;rotation:number;text_status:string;warnings:string[]}[];
  blocks:Block[]; sections:Section[]; warnings:string[];
};
export type Sample = { id:string; paper:{id:string;title:string;page_count:number;original_pdf_url:string}; label:string; synthetic:boolean };
