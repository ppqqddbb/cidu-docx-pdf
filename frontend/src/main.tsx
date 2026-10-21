import React, { ChangeEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlertCircle, ArrowDownToLine, CheckCircle2, FileJson, Loader2, Upload } from "lucide-react";
import "./styles.css";

type SourceRange = {
  document_id: string;
  block_ids: string[];
  page_index: number | null;
  start_offset: number | null;
  end_offset: number | null;
  bbox: unknown;
  preview_bbox?: unknown;
  preview_bboxes?: unknown[];
};

type Change = {
  id: string;
  type: "INSERT" | "DELETE";
  text: string;
  old: SourceRange;
  new: SourceRange;
  confidence: number;
  metadata: Record<string, unknown>;
};

type CompareResult = {
  comparison_id: string;
  quality: {
    old: Record<string, unknown>;
    new: Record<string, unknown>;
    warnings: string[];
  };
  summary: {
    insert_count: number;
    delete_count: number;
    equal_count: number;
    modified_regions: number;
  };
  changes: Change[];
};

type ApiResponse = {
  comparison_id?: string;
  old_document: StructuredDocument;
  new_document: StructuredDocument;
  previews?: {
    old: PreviewDocument;
    new: PreviewDocument;
  };
  result: CompareResult;
};

type PreviewPage = {
  page_index: number;
  image_url: string;
  width: number;
  height: number;
};

type PreviewDocument = {
  pages: PreviewPage[];
};

type StructuredBlock = {
  type?: string;
  content?: unknown;
  text?: string;
  bbox?: unknown;
  [key: string]: unknown;
};

type StructuredPage = {
  page_idx?: number;
  page_no?: number;
  blocks?: StructuredBlock[];
  items?: StructuredBlock[];
};

type StructuredDocument = {
  pages?: StructuredPage[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};

type PreviewBlock = {
  id: string;
  pageIndex: number | null;
  orderIndex: number;
  type: string;
  text: string;
};

type UploadSide = "old" | "new";

function App() {
  const [files, setFiles] = useState<Record<UploadSide, File | null>>({ old: null, new: null });
  const [data, setData] = useState<ApiResponse | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState("");
  const [activeChange, setActiveChange] = useState<string | null>(null);
  const [navigationEpoch, setNavigationEpoch] = useState(0);

  function navigateToChange(id: string) {
    setActiveChange(id);
    // A separate navigation signal makes clicking an already-active box
    // perform the jump again instead of being ignored by React state.
    setNavigationEpoch((value) => value + 1);
  }

  async function submit() {
    if (!files.old || !files.new) return;
    setStatus("loading");
    setError("");
    const form = new FormData();
    form.append("old_file", files.old);
    form.append("new_file", files.new);
    try {
      const response = await fetch("/api/compare-documents", { method: "POST", body: form });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }
      const payload = (await response.json()) as ApiResponse;
      setData(payload);
      setActiveChange(payload.result.changes[0]?.id ?? null);
      setStatus("idle");
    } catch (exc) {
      setStatus("error");
      setError(exc instanceof Error ? exc.message : "compare failed");
    }
  }

  const canSubmit = Boolean(files.old && files.new && status !== "loading");

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>文档内容对比</h1>
          <p>上传 DOCX/PDF 后由 MinerU 生成 Markdown，对比识别内容并回标原文</p>
        </div>
        <div className="status-pill">
          {data ? <CheckCircle2 size={16} /> : <FileJson size={16} />}
          {data ? "READY" : "DOCX/PDF"}
        </div>
      </header>

      <section className="upload-strip">
        <FilePicker label="旧文档" side="old" file={files.old} onPick={(side, file) => setFiles((prev) => ({ ...prev, [side]: file }))} />
        <FilePicker label="新文档" side="new" file={files.new} onPick={(side, file) => setFiles((prev) => ({ ...prev, [side]: file }))} />
        <button className="primary-button" disabled={!canSubmit} onClick={submit} title="开始对比">
          {status === "loading" ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
          对比
        </button>
      </section>

      {status === "error" && (
        <div className="error-line">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {data ? (
        <ComparisonWorkspace data={data} activeChange={activeChange} navigationEpoch={navigationEpoch} onSelectChange={navigateToChange} />
      ) : (
        <EmptyState />
      )}
    </main>
  );
}

function FilePicker({ label, side, file, onPick }: { label: string; side: UploadSide; file: File | null; onPick: (side: UploadSide, file: File | null) => void }) {
  function onChange(event: ChangeEvent<HTMLInputElement>) {
    onPick(side, event.target.files?.[0] ?? null);
  }
  return (
    <label className="file-picker">
      <span>{label}</span>
      <input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={onChange} />
      <strong>{file?.name || "选择文件"}</strong>
    </label>
  );
}

function ComparisonWorkspace({ data, activeChange, navigationEpoch, onSelectChange }: { data: ApiResponse; activeChange: string | null; navigationEpoch: number; onSelectChange: (id: string) => void }) {
  const groups = useMemo(() => groupChanges(data.result.changes), [data.result.changes]);
  const groupByChange = useMemo(() => {
    const mapping = new Map<string, string>();
    groups.forEach((group) => group.changes.forEach((change) => mapping.set(change.id, group.id)));
    return mapping;
  }, [groups]);
  useEffect(() => {
    if (!activeChange) return;
    const targets = document.querySelectorAll<HTMLElement>(`[data-change-id="${activeChange}"]`);
    targets.forEach((target) => {
      const pane = target.closest<HTMLElement>(".doc-pane");
      const scroller = pane?.querySelector<HTMLElement>(".pages");
      const page = target.closest<HTMLElement>(".preview-page");
      if (!scroller || !page) return;
      const top = Math.max(0, page.offsetTop + target.offsetTop - scroller.clientHeight / 2);
      scroller.scrollTo({ top, behavior: "smooth" });
    });
    const changeCard = document.querySelector<HTMLElement>(`[data-change-group="${activeChange}"]`);
    const changeList = changeCard?.closest<HTMLElement>(".change-list");
    if (changeCard && changeList) {
      const top = Math.max(0, changeCard.offsetTop - changeList.offsetTop - changeList.clientHeight / 2 + changeCard.clientHeight / 2);
      changeList.scrollTo({ top, behavior: "smooth" });
    }
  }, [activeChange, navigationEpoch]);

  return (
    <section className="workspace">
      <aside className="change-panel">
        <Summary result={data.result} />
        <div className="change-list">
          {groups.map((group) => (
            <button key={group.id} data-change-group={group.id} className={`change-item ${group.kind.toLowerCase()} ${activeChange === group.id ? "active" : ""}`} onClick={() => onSelectChange(group.id)}>
              <span>{group.kind === "MODIFY" ? "双侧修改" : group.kind === "INSERT" ? "仅新文档" : "仅旧文档"}</span>
              {group.oldText && <strong className="old-change-text">− {group.oldText}</strong>}
              {group.newText && <strong className="new-change-text">+ {group.newText}</strong>}
              {!group.changes.some(hasPreviewTarget) && <em>未定位到页内文字</em>}
            </button>
          ))}
        </div>
      </aside>
      <div className="document-grid">
        <DocumentPane title="旧文档" side="old" preview={data.previews?.old} changes={data.result.changes} groupByChange={groupByChange} activeChange={activeChange} onSelectChange={onSelectChange} />
        <DocumentPane title="新文档" side="new" preview={data.previews?.new} changes={data.result.changes} groupByChange={groupByChange} activeChange={activeChange} onSelectChange={onSelectChange} />
      </div>
    </section>
  );
}

function Summary({ result }: { result: CompareResult }) {
  return (
    <div className="summary">
      <div>
        <span>仅新文档</span>
        <strong>{result.summary.insert_count}</strong>
      </div>
      <div>
        <span>仅旧文档</span>
        <strong>{result.summary.delete_count}</strong>
      </div>
      <div>
        <span>双侧修改</span>
        <strong>{result.summary.modified_regions}</strong>
      </div>
    </div>
  );
}

function DocumentPane({
  title,
  side,
  preview,
  changes,
  groupByChange,
  activeChange,
  onSelectChange
}: {
  title: string;
  side: "old" | "new";
  preview?: PreviewDocument;
  changes: Change[];
  groupByChange: Map<string, string>;
  activeChange: string | null;
  onSelectChange: (id: string) => void;
}) {
  const pages = preview?.pages ?? [];
  const highlights = useMemo(() => buildPageHighlights(changes, side, groupByChange), [changes, side, groupByChange]);
  const unlocated = useMemo(
    () => changes.filter((change) => (
      (side === "old" && change.type === "DELETE") || (side === "new" && change.type === "INSERT")
    ) && !hasSidePreviewTarget(change, side)),
    [changes, side]
  );
  const groupOperationKinds = useMemo(() => {
    const kinds = new Map<string, Set<Change["type"]>>();
    changes.forEach((change) => {
      const groupId = groupByChange.get(change.id) ?? change.id;
      const values = kinds.get(groupId) ?? new Set<Change["type"]>();
      values.add(change.type);
      kinds.set(groupId, values);
    });
    return kinds;
  }, [changes, groupByChange]);
  const absentOnThisSide = useMemo(
    () => changes.filter((change) => (
      (side === "old" && change.type === "INSERT") || (side === "new" && change.type === "DELETE")
    ) && (groupOperationKinds.get(groupByChange.get(change.id) ?? change.id)?.size ?? 0) === 1),
    [changes, side, groupByChange, groupOperationKinds]
  );

  return (
    <section className="doc-pane">
      <header>
        <div>
          <h2>{title}</h2>
          <small>{side === "old" ? "红框：旧文档独有或修改前" : "绿框：新文档独有或修改后"}</small>
        </div>
        <span>{pages.length} pages</span>
      </header>
      {unlocated.length > 0 && (
        <div className={`unlocated-rail ${side}`}>
          <div className="unlocated-title">未能精确落框的{side === "old" ? "删除" : "新增"}（{unlocated.length}）</div>
          <div className="unlocated-items">
            {unlocated.map((change) => {
              const groupId = groupByChange.get(change.id) ?? change.id;
              return (
                <button key={change.id} className={activeChange === groupId ? "active" : ""} onClick={() => onSelectChange(groupId)}>
                  {side === "old" ? "− " : "+ "}{change.text}
                </button>
              );
            })}
          </div>
        </div>
      )}
      {absentOnThisSide.length > 0 && (
        <div className="counterpart-rail">
          <div className="unlocated-title">另一侧独有内容在本侧的空位标记（{absentOnThisSide.length}）</div>
          <div className="unlocated-items">
            {absentOnThisSide.map((change) => {
              const groupId = groupByChange.get(change.id) ?? change.id;
              return (
                <button key={`gap-${change.id}`} className={`gap-marker ${activeChange === groupId ? "active" : ""}`} onClick={() => onSelectChange(groupId)}>
                  {side === "old" ? "此侧无新增文字：" : "此侧无已删除文字："}{change.text}
                </button>
              );
            })}
          </div>
        </div>
      )}
      <div className="pages">
        {pages.length ? (
          pages.map((page) => (
            <article className="preview-page" key={`${side}-${page.page_index}`}>
              <div className="page-label">Page {page.page_index + 1}</div>
              <div className="page-image-wrap" style={{ aspectRatio: `${page.width} / ${page.height}` }}>
                <img src={page.image_url} alt={`${title} page ${page.page_index + 1}`} />
                {(highlights.get(page.page_index) ?? []).map((highlight) => {
                  const rect = bboxToPercentRect(highlight.bbox);
                  if (!rect) return null;
                  return (
                    <button
                      key={`${highlight.changeId}-${highlight.index}`}
                      data-change-id={highlight.changeId}
                      className={`page-highlight ${highlight.type.toLowerCase()} ${activeChange === highlight.changeId ? "active-mark" : ""}`}
                      style={{ left: `${rect.left}%`, top: `${rect.top}%`, width: `${rect.width}%`, height: `${rect.height}%` }}
                      title={`${highlight.type}: ${highlight.text}`}
                      aria-label={`跳转到对应差异：${highlight.text}`}
                      onClick={() => onSelectChange(highlight.changeId)}
                    />
                  );
                })}
              </div>
            </article>
          ))
        ) : (
          <div className="preview-unavailable">暂无原文页图预览</div>
        )}
      </div>
    </section>
  );
}

type PageHighlight = {
  changeId: string;
  type: "INSERT" | "DELETE";
  text: string;
  pageIndex: number;
  bbox: unknown;
  index: number;
};

function buildPageHighlights(changes: Change[], side: "old" | "new", groupByChange: Map<string, string>) {
  const index = new Map<number, PageHighlight[]>();
  changes.forEach((change, changeIndex) => {
    const source = side === "old" ? change.old : change.new;
    if ((side === "old" && change.type !== "DELETE") || (side === "new" && change.type !== "INSERT")) return;
    // Keep the document readable: one outline per change, even when the
    // locator found several candidate rectangles on the same page.
    const bboxes = [source.preview_bbox ?? source.bbox];
    if (source.page_index === null || !bboxes[0]) return;
    const ranges = index.get(source.page_index) ?? [];
    bboxes.forEach((bbox, bboxIndex) => ranges.push({
      changeId: groupByChange.get(change.id) ?? change.id,
      type: change.type,
      text: change.text,
      pageIndex: source.page_index!,
      bbox,
      index: changeIndex * 10 + bboxIndex
    }));
    index.set(source.page_index, ranges);
  });
  return index;
}

function hasPreviewTarget(change: Change) {
  const source = change.type === "DELETE" ? change.old : change.new;
  return source.page_index !== null && Boolean(source.preview_bbox ?? source.bbox);
}

function hasSidePreviewTarget(change: Change, side: "old" | "new") {
  const source = side === "old" ? change.old : change.new;
  return source.page_index !== null && Boolean(source.preview_bboxes?.length || source.preview_bbox || source.bbox);
}

type ChangeGroup = {
  id: string;
  kind: "INSERT" | "DELETE" | "MODIFY";
  changes: Change[];
  oldText: string;
  newText: string;
};

function groupChanges(changes: Change[]): ChangeGroup[] {
  const groups: ChangeGroup[] = [];
  for (let index = 0; index < changes.length;) {
    const current = changes[index];
    const groupId = typeof current.metadata.group_id === "string" ? current.metadata.group_id : null;
    const members: Change[] = [current];
    let cursor = index + 1;
    if (groupId) {
      while (cursor < changes.length && changes[cursor].metadata.group_id === groupId) {
        members.push(changes[cursor]);
        cursor += 1;
      }
    } else if (cursor < changes.length && changes[cursor].type !== current.type) {
      members.push(changes[cursor]);
      cursor += 1;
    }
    const hasInsert = members.some((change) => change.type === "INSERT");
    const hasDelete = members.some((change) => change.type === "DELETE");
    groups.push({
      id: current.id,
      kind: hasInsert && hasDelete ? "MODIFY" : hasInsert ? "INSERT" : "DELETE",
      changes: members,
      oldText: members.filter((change) => change.type === "DELETE").map((change) => change.text).join(""),
      newText: members.filter((change) => change.type === "INSERT").map((change) => change.text).join("")
    });
    index = cursor;
  }
  return groups;
}

function bboxToPercentRect(bbox: unknown) {
  let values: number[] | null = null;
  if (Array.isArray(bbox) && bbox.length >= 4) {
    values = bbox.slice(0, 4).map(Number);
  } else if (bbox && typeof bbox === "object") {
    const obj = bbox as Record<string, unknown>;
    const raw = obj.normalized || obj.bbox || obj.box;
    if (Array.isArray(raw) && raw.length >= 4) values = raw.slice(0, 4).map(Number);
  }
  if (!values || values.some((value) => !Number.isFinite(value))) return null;
  const [x0, y0, x1, y1] = values;
  const maxValue = Math.max(Math.abs(x0), Math.abs(y0), Math.abs(x1), Math.abs(y1));
  const denominator = maxValue <= 1 ? 1 : 1000;
  const left = clamp((Math.min(x0, x1) / denominator) * 100, 0, 100);
  const top = clamp((Math.min(y0, y1) / denominator) * 100, 0, 100);
  const right = clamp((Math.max(x0, x1) / denominator) * 100, 0, 100);
  const bottom = clamp((Math.max(y0, y1) / denominator) * 100, 0, 100);
  if (right <= left || bottom <= top) return null;
  return { left, top, width: right - left, height: bottom - top };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function EmptyState() {
  return (
    <section className="empty-state">
      <ArrowDownToLine size={28} />
      <h2>上传两个 DOCX/PDF 文档</h2>
      <p>后端会比较 MinerU 生成的 Markdown，并将新增、删除和修改回标到原始页面。</p>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
