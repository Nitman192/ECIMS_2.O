import { useEffect, useState } from 'react';
import { FiCheckSquare, FiDownload, FiPlus, FiRefreshCw, FiSearch, FiUploadCloud } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack } from '../../components/ui/Toast';
import { useToastStack } from '../../hooks/useToastStack';
import { toOptionalFilter, toOptionalQuery } from '../../utils/listQuery';
import type { PatchUpdateItem, StateBackupScope } from '../../types';

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '-');

const formatBytes = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) return '0 B';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
};

const statusBadgeClass = (status: string) => {
  if (status === 'UPLOADED') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  if (status === 'APPLIED') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (status === 'FAILED') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  if (status === 'ROLLED_BACK') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

type UploadForm = {
  version: string;
  notes: string;
  bundle: File | null;
};

const defaultUploadForm: UploadForm = {
  version: '',
  notes: '',
  bundle: null,
};

type ApplyForm = {
  reason: string;
  backupScope: StateBackupScope;
  includeSensitive: boolean;
};

const defaultApplyForm: ApplyForm = {
  reason: '',
  backupScope: 'CONFIG_ONLY',
  includeSensitive: false,
};

export const PatchUpdatesPage = () => {
  const [rows, setRows] = useState<PatchUpdateItem[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadForm, setUploadForm] = useState<UploadForm>(defaultUploadForm);

  const [applyOpen, setApplyOpen] = useState(false);
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyTarget, setApplyTarget] = useState<PatchUpdateItem | null>(null);
  const [applyForm, setApplyForm] = useState<ApplyForm>(defaultApplyForm);

  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 4600 });

  const loadRows = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listPatchUpdates({
        page: 1,
        page_size: 100,
        status: toOptionalFilter(statusFilter),
        q: toOptionalQuery(query),
      });
      setRows(response.data.items ?? []);
      setStatus('ready');
    } catch (error: unknown) {
      setRows([]);
      setStatus('error');
      setErrorMessage(getApiErrorMessage(error, 'Unable to load patch updates'));
    }
  };

  useEffect(() => {
    void loadRows();
  }, []);

  const openUpload = () => {
    setUploadForm(defaultUploadForm);
    setUploadOpen(true);
  };

  const submitUpload = async () => {
    if (uploadForm.version.trim().length < 2) {
      pushToast({ title: 'Version should be at least 2 characters', tone: 'warning' });
      return;
    }
    if (!uploadForm.bundle) {
      pushToast({ title: 'Select a patch package file first', tone: 'warning' });
      return;
    }
    const formData = new FormData();
    formData.append('version', uploadForm.version.trim());
    formData.append('notes', uploadForm.notes.trim());
    formData.append('bundle', uploadForm.bundle, uploadForm.bundle.name);

    setUploadBusy(true);
    try {
      const response = await CoreApi.uploadPatchUpdate(formData);
      setUploadOpen(false);
      await loadRows();
      pushToast({
        title: 'Patch package uploaded',
        description: `Patch ID: ${response.data.item.patch_id}`,
        tone: 'success',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Upload failed', description: getApiErrorMessage(error, 'Unable to upload patch package'), tone: 'error' });
    } finally {
      setUploadBusy(false);
    }
  };

  const downloadPatch = async (row: PatchUpdateItem) => {
    try {
      const response = await CoreApi.downloadPatchUpdate(row.patch_id);
      const blob = new Blob([response.data], { type: 'application/octet-stream' });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = row.filename || `${row.patch_id}.bin`;
      anchor.click();
      window.URL.revokeObjectURL(url);
      pushToast({
        title: 'Patch download started',
        description: row.filename,
        tone: 'info',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Download failed', description: getApiErrorMessage(error, 'Unable to download patch package'), tone: 'error' });
    }
  };

  const openApply = (row: PatchUpdateItem) => {
    setApplyTarget(row);
    setApplyForm(defaultApplyForm);
    setApplyOpen(true);
  };

  const submitApply = async () => {
    if (!applyTarget) return;
    if (applyForm.reason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    setApplyBusy(true);
    try {
      const response = await CoreApi.applyPatchUpdate(applyTarget.patch_id, {
        reason: applyForm.reason.trim(),
        backup_scope: applyForm.backupScope,
        include_sensitive: applyForm.includeSensitive,
      });
      setApplyOpen(false);
      setApplyTarget(null);
      await loadRows();
      pushToast({
        title: 'Patch marked as applied',
        description: `Backup snapshot: ${response.data.backup.backup_id}`,
        tone: 'success',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Patch apply failed', description: getApiErrorMessage(error, 'Unable to apply patch workflow'), tone: 'error' });
    } finally {
      setApplyBusy(false);
    }
  };

  const columns: DataTableColumn<PatchUpdateItem>[] = [
    {
      key: 'patch_id',
      header: 'Patch',
      render: (row) => (
        <div className="flex max-w-[250px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.patch_id}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.version}</span>
        </div>
      ),
    },
    {
      key: 'filename',
      header: 'Package',
      render: (row) => (
        <div className="flex max-w-[320px] flex-col">
          <span className="truncate">{row.filename}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{formatBytes(row.file_size_bytes)} | {row.sha256.slice(0, 14)}...</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => formatDate(row.created_at),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex gap-1.5">
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void downloadPatch(row)}>
            <FiDownload className="mr-1 text-xs" />
            Download
          </button>
          {row.status !== 'APPLIED' ? (
            <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openApply(row)}>
              <FiCheckSquare className="mr-1 text-xs" />
              Apply
            </button>
          ) : (
            <span className="inline-flex items-center rounded-lg bg-emerald-100 px-2 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
              Applied
            </span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Patch Updates"
        subtitle="Offline patch package vault for LAN deployment with pre-change backup snapshot and auditable apply workflow."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadRows()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={openUpload}>
              <FiPlus className="mr-2 text-sm" />
              Upload Patch
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_220px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search patch id, version, filename"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="UPLOADED">UPLOADED</option>
            <option value="APPLIED">APPLIED</option>
            <option value="FAILED">FAILED</option>
            <option value="ROLLED_BACK">ROLLED_BACK</option>
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadRows()}>
            Apply
          </button>
        </div>
      </Card>

      <Card title="Patch Package Registry" subtitle="Upload signed patch package, download on target machine, then mark apply after controlled install.">
        {status === 'loading' && <LoadingState title="Loading patches" description="Fetching offline patch updates." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadRows()} />}
        {status === 'ready' && rows.length > 0 && <DataTable columns={columns} rows={rows} rowKey={(row) => row.patch_id} />}
        {status === 'ready' && rows.length === 0 && (
          <EmptyState
            title="No patch packages"
            description="Upload first offline patch package to start controlled rollout."
            actionLabel="Upload Patch"
            onAction={openUpload}
          />
        )}
      </Card>

      <Modal
        open={uploadOpen}
        title="Upload Patch Package"
        description="Attach offline patch file bundle for LAN distribution."
        confirmLabel={uploadBusy ? 'Uploading...' : 'Upload'}
        confirmDisabled={uploadBusy}
        cancelLabel="Cancel"
        cancelDisabled={uploadBusy}
        onCancel={() => setUploadOpen(false)}
        onConfirm={() => void submitUpload()}
      >
        <div className="space-y-3">
          <input
            className="input"
            value={uploadForm.version}
            onChange={(event) => setUploadForm((prev) => ({ ...prev, version: event.target.value }))}
            placeholder="Version (example: 2.0.1-hotfix1)"
          />
          <textarea
            className="input min-h-[88px] resize-y"
            value={uploadForm.notes}
            onChange={(event) => setUploadForm((prev) => ({ ...prev, notes: event.target.value }))}
            placeholder="Notes (optional)"
          />
          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400">
              Patch file bundle
            </span>
            <input
              type="file"
              className="input cursor-pointer file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-slate-800 dark:file:bg-slate-100 dark:file:text-slate-900 dark:hover:file:bg-white"
              onChange={(event) => setUploadForm((prev) => ({ ...prev, bundle: event.target.files?.[0] ?? null }))}
            />
          </label>
        </div>
      </Modal>

      <Modal
        open={applyOpen}
        title={applyTarget ? `Apply Workflow - ${applyTarget.patch_id}` : 'Apply Workflow'}
        description="Create pre-change backup and mark patch as applied in audit timeline."
        confirmLabel={applyBusy ? 'Applying...' : 'Apply'}
        confirmDisabled={applyBusy}
        cancelLabel="Cancel"
        cancelDisabled={applyBusy}
        onCancel={() => {
          setApplyOpen(false);
          setApplyTarget(null);
        }}
        onConfirm={() => void submitApply()}
      >
        <div className="space-y-3">
          <textarea
            className="input min-h-[84px] resize-y"
            value={applyForm.reason}
            onChange={(event) => setApplyForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="Apply reason (min 5 chars)"
          />
          <select
            className="input"
            value={applyForm.backupScope}
            onChange={(event) => setApplyForm((prev) => ({ ...prev, backupScope: event.target.value as StateBackupScope }))}
          >
            <option value="CONFIG_ONLY">CONFIG_ONLY backup</option>
            <option value="FULL">FULL backup</option>
          </select>
          <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
            <input
              type="checkbox"
              checked={applyForm.includeSensitive}
              onChange={(event) => setApplyForm((prev) => ({ ...prev, includeSensitive: event.target.checked }))}
            />
            Include sensitive fields in backup snapshot
          </label>
        </div>
      </Modal>

      <Card>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            <FiUploadCloud className="mr-2 inline text-sm" />
            LAN patch workflow
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            1) Upload patch package in this panel.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            2) Download and install patch on target LAN endpoint.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            3) Use Apply to create rollback backup snapshot and close rollout audit trail.
          </p>
        </div>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};

