"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { useProjectStore } from "@/stores/project";

type Preview = {
  owner: string;
  repo: string;
  commit_sha: string;
  files: { path: string }[];
  excluded: { path: string; reason: string }[];
  included_files: number;
  excluded_files: number;
};
type Job = {
  state: "running" | "completed" | "failed" | "cancelled";
  total_files: number;
  processed_files: number;
  failed_files: number;
  message: string;
  errors: { path?: string; reason?: string; error?: string }[];
};

export default function RepositoryPage() {
  const { activeProjectId, loadProjects } = useProjectStore();
  const [client] = useState(() => createClient());

  useEffect(() => {
    if (activeProjectId) return;
    void client.auth.getSession().then(({ data }) => {
      if (data.session) return loadProjects(data.session.access_token);
    }).catch(() => undefined);
  }, [activeProjectId, client, loadProjects]);

  return (
    <>
      <DashboardHeader title="Repository" />
      <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        <h1 className="text-2xl font-semibold">Import a GitHub repository</h1>
        {activeProjectId ? (
          <RepositoryImport key={activeProjectId} projectId={activeProjectId} client={client} />
        ) : <p>Select or create a project to import repository files.</p>}
      </main>
    </>
  );
}

function RepositoryImport({ projectId, client }: {
  projectId: string;
  client: ReturnType<typeof createClient>;
}) {
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("");
  const [include, setInclude] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const terminal = job !== null && job.state !== "running";

  async function token() {
    const { data } = await client.auth.getSession();
    if (!data.session) throw new Error("Sign in to import a repository.");
    return data.session.access_token;
  }

  useEffect(() => {
    if (!jobId || terminal) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const { data } = await client.auth.getSession();
        if (controller.signal.aborted) return;
        if (!data.session) throw new Error("Sign in again to view import progress.");
        const result = await apiFetch<Job>("/github/import/" + encodeURIComponent(jobId), {
          token: data.session.access_token, projectId, signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setJob(result);
        setError("");
        if (result.state !== "running") return;
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Could not load import progress.");
      }
      timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [client, jobId, projectId, terminal]);

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const importing = !event;
    if (busy || (jobId && !terminal) || (importing && !preview?.included_files)) return;
    setBusy(true);
    setError("");
    try {
      const options = {
        method: "POST",
        token: await token(),
        projectId,
        timeoutMs: 60000,
        body: {
          repo_url: url.trim(),
          ref: importing ? preview?.commit_sha : ref.trim() || null,
          include: include.split(",").map((pattern) => pattern.trim()).filter(Boolean),
        },
      };
      if (!options.body.include.length) Object.assign(options.body, { include: null });
      if (importing) {
        const result = await apiFetch<{ job_id: string }>("/github/import/repository", options);
        setJob(null);
        setJobId(result.job_id);
      } else {
        setPreview(await apiFetch<Preview>("/github/import/preview", options));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Repository request failed.");
    } finally {
      setBusy(false);
    }
  }

  const running = Boolean(jobId && !terminal);
  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="space-y-4 rounded-xl border p-5">
        <p className="text-sm text-muted-foreground">Import selected files from a public repository into this project.</p>
        <fieldset disabled={busy || running} className="space-y-4">
          <label className="block space-y-1">
            <span>Repository URL</span>
            <Input type="url" required placeholder="https://github.com/owner/repository" value={url}
              onChange={(event) => { setUrl(event.target.value); setPreview(null); }} />
          </label>
          <label className="block space-y-1">
            <span>Branch, tag, or commit (optional)</span>
            <Input placeholder="Repository default branch" value={ref}
              onChange={(event) => { setRef(event.target.value); setPreview(null); }} />
          </label>
          <label className="block space-y-1">
            <span>Include patterns (optional, comma separated)</span>
            <Input placeholder="README.md, docs/*.md" value={include}
              onChange={(event) => { setInclude(event.target.value); setPreview(null); }} />
          </label>
          <Button type="submit">{busy ? "Working…" : "Preview files"}</Button>
        </fieldset>
      </form>

      {preview && <section className="space-y-3 rounded-xl border p-5">
        <h2 className="font-semibold">{preview.owner}/{preview.repo}</h2>
        <p className="break-all text-sm">Commit {preview.commit_sha}</p>
        <p>{preview.included_files} eligible · {preview.excluded_files} skipped</p>
        <ul aria-label="Eligible files" className="max-h-48 list-inside list-disc overflow-auto break-all text-sm">
          {preview.files.map((file) => <li key={file.path}>{file.path}</li>)}
        </ul>
        {preview.excluded.length > 0 && <details>
          <summary>Skipped files</summary>
          <ul className="max-h-48 overflow-auto break-all text-sm">
            {preview.excluded.map((file) => <li key={file.path}>{file.path} — {file.reason}</li>)}
          </ul>
        </details>}
        <Button disabled={busy || running || !preview.included_files} onClick={() => void submit()}>
          Import {preview.included_files} files
        </Button>
      </section>}

      {jobId && <section className="space-y-2 rounded-xl border p-5" aria-live="polite">
        <h2 className="font-semibold">Import progress</h2>
        <p>{job ? job.message || job.state : "Waiting for import status…"}</p>
        {job && <>
          <progress className="w-full" aria-label="Files handled" max={job.total_files || 1}
            value={job.processed_files + job.failed_files} />
          <p>{job.processed_files} processed · {job.failed_files} failed · {job.total_files} total</p>
          <ul className="list-inside list-disc break-all text-sm">
            {job.errors.map((item, index) => <li key={index}>{item.path} — {item.reason || item.error}</li>)}
          </ul>
        </>}
        {terminal && <p className="flex gap-4">
          <Link className="underline" href="/documents">Open Documents</Link>
          <Link className="underline" href="/graph">Explore Graph</Link>
        </p>}
      </section>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
