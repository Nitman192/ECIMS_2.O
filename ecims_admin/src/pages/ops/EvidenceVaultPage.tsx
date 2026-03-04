import { useEffect, useMemo, useState } from 'react';
import {
  FiArchive,
  FiCopy,
  FiDownload,
  FiEye,
  FiFilePlus,
  FiLink,
  FiPlus,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiUpload,
} from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack, type ToastItem } from '../../components/ui/Toast';
import type {
  EvidenceClassification,
  EvidenceCustodyEvent,
  EvidenceCustodyEventCreatePayload,
  EvidenceObject,
  EvidenceOriginType,
} from '../../types';

const originOptions: Array<{ value: EvidenceOriginType; label: string }> = [
  { value: 'ALERT', label: 'Alert' },
  { value: 'EVENT', label: 'Event' },
  { value: 'AGENT', label: 'Agent' },
  { value: 'MANUAL', label: 'Manual' },
  { value: 'FORENSICS_IMPORT', label: 'Forensics Import' },
];

const classificationOptions: Array<{ value: EvidenceClassification; label: string }> = [
  { value: 'INTERNAL', label: 'Internal' },
  { value: 'CONFIDENTIAL', label: 'Confidential' },
  { value: 'RESTRICTED', label: 'Restricted' },
];

const custodyEventOptions: Array<{ value: EvidenceCustodyEventCreatePayload['event_type']; label: string }> = [
  { value: 'REVIEW_STARTED', label: 'Review Started' },
  { value: 'RESEALED', label: 'Resealed' },
  { value: 'RELEASED', label: 'Released' },
  { value: 'ARCHIVED', label: 'Archived' },
  { value: 'NOTE_ADDED', label: 'Note Added' },
  { value: 'TRANSFERRED', label: 'Transferred' },
];

const makeIdempotencyKey = () => `evidence-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const parseError = (error: any, fallback: string) => error?.response?.data?.detail || error?.message || fallback;

const statusBadgeClass = (status: string) => {
  if (status === 'SEALED') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (status === 'IN_REVIEW') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  if (status === 'RELEASED') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const originBadgeClass = (origin: string) => {
  if (origin === 'ALERT') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  if (origin === 'EVENT') return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300';
  if (origin === 'AGENT') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  if (origin === 'FORENSICS_IMPORT') return 'bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const parseJsonObject = (raw: string): Record<string, unknown> => {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON object expected');
  }
  return parsed as Record<string, unknown>;
};

const downloadJson = (filename: string, payload: unknown) => {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

type CreateForm = {
  objectHash: string;
  originType: EvidenceOriginType;
  originRef: string;
  classification: EvidenceClassification;
  reason: string;
  idempotencyKey: string;
  manifestJson: string;
  metadataJson: string;
};

const defaultCreateForm: CreateForm = {
  objectHash: '',
  originType: 'MANUAL',
  originRef: '',
  classification: 'INTERNAL',
  reason: '',
  idempotencyKey: makeIdempotencyKey(),
  manifestJson: '{}',
  metadataJson: '{"source":"admin-console"}',
};

type CustodyForm = {
  eventType: EvidenceCustodyEventCreatePayload['event_type'];
  reason: string;
  detailsJson: string;
};

const defaultCustodyForm: CustodyForm = {
  eventType: 'NOTE_ADDED',
  reason: '',
  detailsJson: '{}',
};

export const EvidenceVaultPage = () => {
  const [rows, setRows] = useState<EvidenceObject[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [originFilter, setOriginFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(defaultCreateForm);

  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceObject | null>(null);

  const [timelineOpen, setTimelineOpen] = useState(false);
  const [timelineBusy, setTimelineBusy] = useState(false);
  const [timelineError, setTimelineError] = useState('');
  const [timelineRows, setTimelineRows] = useState<EvidenceCustodyEvent[]>([]);
  const [timelineChainValid, setTimelineChainValid] = useState<boolean>(true);

  const [custodyOpen, setCustodyOpen] = useState(false);
  const [custodyBusy, setCustodyBusy] = useState(false);
  const [custodyForm, setCustodyForm] = useState<CustodyForm>(defaultCustodyForm);

  const [exportOpen, setExportOpen] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportReason, setExportReason] = useState('');
  const [exportResultOpen, setExportResultOpen] = useState(false);
  const [exportHash, setExportHash] = useState('');
  const [exportBundle, setExportBundle] = useState<Record<string, unknown> | null>(null);

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 4200);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  };

  const loadEvidence = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listEvidenceVault({
        page: 1,
        page_size: 100,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        origin: originFilter !== 'all' ? originFilter : undefined,
        q: query.trim() ? query.trim() : undefined,
      });
      setRows(response.data.items ?? []);
      setStatus('ready');
    } catch (error: any) {
      setRows([]);
      setStatus('error');
      setErrorMessage(parseError(error, 'Unable to load evidence vault objects'));
    }
  };

  useEffect(() => {
    void loadEvidence();
  }, []);

  const filteredRows = useMemo(() => rows, [rows]);

  const openCreateModal = () => {
    setCreateForm({ ...defaultCreateForm, idempotencyKey: makeIdempotencyKey() });
    setCreateOpen(true);
  };

  const submitCreateEvidence = async () => {
    const hash = createForm.objectHash.trim().toLowerCase();
    if (!/^[a-f0-9]{64}$/.test(hash)) {
      pushToast({ title: 'Valid SHA256 hash required', tone: 'warning' });
      return;
    }
    if (createForm.reason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    let manifest: Record<string, unknown>;
    let metadata: Record<string, unknown>;
    try {
      manifest = parseJsonObject(createForm.manifestJson);
      metadata = parseJsonObject(createForm.metadataJson);
    } catch {
      pushToast({ title: 'Manifest/Metadata JSON is invalid', tone: 'warning' });
      return;
    }

    setCreateBusy(true);
    try {
      const response = await CoreApi.createEvidenceObject({
        object_hash: hash,
        hash_algorithm: 'SHA256',
        origin_type: createForm.originType,
        origin_ref: createForm.originRef.trim() || null,
        classification: createForm.classification,
        reason: createForm.reason.trim(),
        idempotency_key: createForm.idempotencyKey.trim(),
        manifest,
        metadata,
      });
      setCreateOpen(false);
      await loadEvidence();
      pushToast({
        title: response.data.created ? 'Evidence object registered' : 'Idempotent replay returned existing object',
        description: `Evidence ID: ${response.data.item.evidence_id}`,
        tone: response.data.created ? 'success' : 'info',
      });
    } catch (error: any) {
      pushToast({ title: 'Create evidence failed', description: parseError(error, 'Unable to register evidence object'), tone: 'error' });
    } finally {
      setCreateBusy(false);
    }
  };

  const openTimeline = async (row: EvidenceObject) => {
    setSelectedEvidence(row);
    setTimelineOpen(true);
    setTimelineBusy(true);
    setTimelineError('');
    setTimelineRows([]);
    setTimelineChainValid(true);
    try {
      const response = await CoreApi.getEvidenceTimeline(row.evidence_id);
      setTimelineRows(response.data.items ?? []);
      setTimelineChainValid(Boolean(response.data.chain_valid));
    } catch (error: any) {
      setTimelineError(parseError(error, 'Unable to load custody timeline'));
    } finally {
      setTimelineBusy(false);
    }
  };

  const openCustodyModal = (row: EvidenceObject) => {
    setSelectedEvidence(row);
    setCustodyForm(defaultCustodyForm);
    setCustodyOpen(true);
  };

  const submitCustodyEvent = async () => {
    if (!selectedEvidence) return;
    if (custodyForm.reason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    let details: Record<string, unknown>;
    try {
      details = parseJsonObject(custodyForm.detailsJson);
    } catch {
      pushToast({ title: 'Event details JSON is invalid', tone: 'warning' });
      return;
    }

    setCustodyBusy(true);
    try {
      await CoreApi.appendEvidenceCustodyEvent(selectedEvidence.evidence_id, {
        event_type: custodyForm.eventType,
        reason: custodyForm.reason.trim(),
        details,
      });
      setCustodyOpen(false);
      await loadEvidence();
      pushToast({
        title: 'Custody event appended',
        description: `${custodyForm.eventType} recorded for ${selectedEvidence.evidence_id}`,
        tone: 'success',
      });
      await openTimeline(selectedEvidence);
    } catch (error: any) {
      pushToast({ title: 'Append custody event failed', description: parseError(error, 'Unable to append custody event'), tone: 'error' });
    } finally {
      setCustodyBusy(false);
    }
  };

  const openExportModal = (row: EvidenceObject) => {
    setSelectedEvidence(row);
    setExportReason('');
    setExportOpen(true);
  };

  const submitExport = async () => {
    if (!selectedEvidence) return;
    if (exportReason.trim().length < 5) {
      pushToast({ title: 'Export reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    setExportBusy(true);
    try {
      const response = await CoreApi.exportEvidenceBundle(selectedEvidence.evidence_id, { reason: exportReason.trim() });
      setExportOpen(false);
      setExportHash(response.data.export_hash);
      setExportBundle(response.data.bundle as unknown as Record<string, unknown>);
      setExportResultOpen(true);
      pushToast({
        title: 'Evidence bundle exported',
        description: `Export hash: ${response.data.export_hash.slice(0, 16)}...`,
        tone: 'success',
      });
      await loadEvidence();
    } catch (error: any) {
      pushToast({ title: 'Export failed', description: parseError(error, 'Unable to export evidence bundle'), tone: 'error' });
    } finally {
      setExportBusy(false);
    }
  };

  const copyText = async (value: string, label: string) => {
    try {
      if (!navigator.clipboard) {
        pushToast({ title: `${label} copy unavailable`, tone: 'warning' });
        return;
      }
      await navigator.clipboard.writeText(value);
      pushToast({ title: `${label} copied`, tone: 'success' });
    } catch {
      pushToast({ title: `${label} copy failed`, tone: 'error' });
    }
  };

  const evidenceColumns: DataTableColumn<EvidenceObject>[] = [
    {
      key: 'evidence_id',
      header: 'Evidence',
      render: (row) => (
        <div className="flex max-w-[240px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.evidence_id}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.object_hash}</span>
        </div>
      ),
    },
    {
      key: 'origin_type',
      header: 'Origin',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${originBadgeClass(row.origin_type)}`}>
          {row.origin_type}
        </span>
      ),
    },
    {
      key: 'classification',
      header: 'Classification',
      render: (row) => <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{row.classification}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>
      ),
    },
    { key: 'created_by_username', header: 'Owner', render: (row) => row.created_by_username || `User #${row.created_by_user_id}` },
    { key: 'created_at', header: 'Registered', render: (row) => formatDate(row.created_at) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1.5">
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void openTimeline(row)}>
            <FiEye className="mr-1 text-xs" />
            Timeline
          </button>
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openCustodyModal(row)}>
            <FiLink className="mr-1 text-xs" />
            Custody
          </button>
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openExportModal(row)}>
            <FiDownload className="mr-1 text-xs" />
            Export
          </button>
        </div>
      ),
    },
  ];

  const timelineColumns: DataTableColumn<EvidenceCustodyEvent>[] = [
    { key: 'sequence_no', header: '#' },
    { key: 'event_type', header: 'Event' },
    {
      key: 'actor',
      header: 'Actor',
      render: (row) => row.actor_username || (row.actor_user_id ? `User #${row.actor_user_id}` : row.actor_role),
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (row) => <span className="max-w-[260px] truncate">{row.reason}</span>,
    },
    { key: 'event_ts', header: 'Timestamp', render: (row) => formatDate(row.event_ts) },
    {
      key: 'event_hash',
      header: 'Event Hash',
      render: (row) => <span className="max-w-[180px] truncate font-mono text-xs">{row.event_hash}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence Vault"
        subtitle="Immutable evidence objects with append-only chain-of-custody timeline, integrity checks, and controlled export."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadEvidence()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={openCreateModal}>
              <FiPlus className="mr-2 text-sm" />
              Register Evidence
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_180px_180px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search evidence id, hash, origin ref"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="SEALED">SEALED</option>
            <option value="IN_REVIEW">IN_REVIEW</option>
            <option value="RELEASED">RELEASED</option>
            <option value="ARCHIVED">ARCHIVED</option>
          </select>

          <select
            value={originFilter}
            onChange={(event) => setOriginFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Origins</option>
            {originOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.value}
              </option>
            ))}
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadEvidence()}>
            Apply
          </button>
        </div>
      </Card>

      <Card title="Evidence Inventory" subtitle="Tamper-evident records for incident forensics and compliance exports.">
        {status === 'loading' && <LoadingState title="Loading evidence vault" description="Fetching immutable evidence records." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadEvidence()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={evidenceColumns} rows={filteredRows} rowKey={(row) => row.evidence_id} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No evidence objects"
            description="Register your first evidence object to start a custody chain."
            actionLabel="Register Evidence"
            onAction={openCreateModal}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Register Evidence Object"
        description="Create immutable evidence record with canonical hash, origin metadata, and first custody entry."
        confirmLabel={createBusy ? 'Registering...' : 'Register'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (createBusy) return;
          setCreateOpen(false);
        }}
        onConfirm={() => void submitCreateEvidence()}
      >
        <div className="space-y-3">
          <input
            className="input font-mono"
            value={createForm.objectHash}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, objectHash: event.target.value }))}
            placeholder="SHA256 object hash (64 hex chars)"
          />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.originType}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, originType: event.target.value as EvidenceOriginType }))}
            >
              {originOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <select
              className="input"
              value={createForm.classification}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, classification: event.target.value as EvidenceClassification }))
              }
            >
              {classificationOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <input
            className="input"
            value={createForm.originRef}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, originRef: event.target.value }))}
            placeholder="Origin reference (alert id, case id, etc)"
          />

          <textarea
            className="input min-h-[84px] resize-y"
            value={createForm.reason}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="Reason (min 5 chars)"
          />

          <input
            className="input"
            value={createForm.idempotencyKey}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, idempotencyKey: event.target.value }))}
            placeholder="Idempotency key"
          />

          <textarea
            className="input min-h-[92px] resize-y font-mono text-xs"
            value={createForm.manifestJson}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, manifestJson: event.target.value }))}
            placeholder="Manifest JSON (optional signed manifest metadata)"
          />

          <textarea
            className="input min-h-[92px] resize-y font-mono text-xs"
            value={createForm.metadataJson}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, metadataJson: event.target.value }))}
            placeholder="Metadata JSON"
          />
        </div>
      </Modal>

      <Modal
        open={timelineOpen}
        title={selectedEvidence ? `Custody Timeline - ${selectedEvidence.evidence_id}` : 'Custody Timeline'}
        description="Append-only chain events with hash-link verification."
        cancelLabel="Close"
        onCancel={() => {
          setTimelineOpen(false);
          setTimelineRows([]);
          setTimelineError('');
          setSelectedEvidence(null);
        }}
      >
        <div className="space-y-3">
          <div
            className={`rounded-xl border px-3 py-2 text-xs ${
              timelineChainValid
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300'
                : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300'
            }`}
          >
            Chain integrity: {timelineChainValid ? 'VALID' : 'INVALID - potential tamper detected'}
          </div>

          {timelineBusy && <LoadingState title="Loading custody timeline" description="Fetching chronological custody events." />}
          {!timelineBusy && timelineError && <ErrorState description={timelineError} onRetry={() => selectedEvidence && void openTimeline(selectedEvidence)} />}
          {!timelineBusy && !timelineError && timelineRows.length > 0 && (
            <DataTable columns={timelineColumns} rows={timelineRows} rowKey={(row) => `${row.evidence_id}-${row.sequence_no}`} />
          )}
          {!timelineBusy && !timelineError && timelineRows.length === 0 && (
            <EmptyState title="No custody events" description="No custody events were recorded for this evidence object." />
          )}
        </div>
      </Modal>

      <Modal
        open={custodyOpen}
        title={selectedEvidence ? `Append Custody Event - ${selectedEvidence.evidence_id}` : 'Append Custody Event'}
        description="Add signed chain event for review, transfer, release, or archival actions."
        confirmLabel={custodyBusy ? 'Appending...' : 'Append Event'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (custodyBusy) return;
          setCustodyOpen(false);
        }}
        onConfirm={() => void submitCustodyEvent()}
      >
        <div className="space-y-3">
          <select
            className="input"
            value={custodyForm.eventType}
            onChange={(event) =>
              setCustodyForm((prev) => ({
                ...prev,
                eventType: event.target.value as EvidenceCustodyEventCreatePayload['event_type'],
              }))
            }
          >
            {custodyEventOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>

          <textarea
            className="input min-h-[84px] resize-y"
            value={custodyForm.reason}
            onChange={(event) => setCustodyForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="Reason (min 5 chars)"
          />

          <textarea
            className="input min-h-[92px] resize-y font-mono text-xs"
            value={custodyForm.detailsJson}
            onChange={(event) => setCustodyForm((prev) => ({ ...prev, detailsJson: event.target.value }))}
            placeholder="Details JSON"
          />
        </div>
      </Modal>

      <Modal
        open={exportOpen}
        title={selectedEvidence ? `Export Evidence - ${selectedEvidence.evidence_id}` : 'Export Evidence'}
        description="Generate canonical export bundle and append export event to custody chain."
        confirmLabel={exportBusy ? 'Exporting...' : 'Export Bundle'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (exportBusy) return;
          setExportOpen(false);
        }}
        onConfirm={() => void submitExport()}
      >
        <textarea
          className="input min-h-[96px] resize-y"
          value={exportReason}
          onChange={(event) => setExportReason(event.target.value)}
          placeholder="Export reason (min 5 chars)"
        />
      </Modal>

      <Modal
        open={exportResultOpen}
        title="Evidence Bundle Exported"
        description="Copy export hash and download bundle payload."
        cancelLabel="Close"
        onCancel={() => {
          setExportResultOpen(false);
          setExportHash('');
          setExportBundle(null);
        }}
      >
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Export Hash</p>
              <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void copyText(exportHash, 'Export hash')}>
                <FiCopy className="mr-1 text-xs" />
                Copy
              </button>
            </div>
            <p className="break-all rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
              {exportHash}
            </p>
          </div>

          {exportBundle && (
            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Bundle JSON</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-secondary h-8 px-2 text-xs"
                    onClick={() => void copyText(JSON.stringify(exportBundle, null, 2), 'Bundle JSON')}
                  >
                    <FiCopy className="mr-1 text-xs" />
                    Copy JSON
                  </button>
                  <button
                    type="button"
                    className="btn-secondary h-8 px-2 text-xs"
                    onClick={() => downloadJson('evidence-bundle.json', exportBundle)}
                  >
                    <FiDownload className="mr-1 text-xs" />
                    Download
                  </button>
                </div>
              </div>
              <textarea readOnly value={JSON.stringify(exportBundle, null, 2)} className="input min-h-[180px] resize-y font-mono text-xs" />
            </div>
          )}
        </div>
      </Modal>

      <Card>
        <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            <FiShield className="mr-2 inline text-sm" />
            Chain-of-custody guardrails
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Evidence records are immutable; custody actions append hash-linked events only.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            <FiFilePlus className="mr-1 inline text-xs" />
            Create endpoint: <code>/api/v1/admin/ops/evidence-vault</code>
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            <FiArchive className="mr-1 inline text-xs" />
            Timeline endpoint: <code>/api/v1/admin/ops/evidence-vault/{'{evidence_id}'}/timeline</code>
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            <FiUpload className="mr-1 inline text-xs" />
            Export endpoint: <code>/api/v1/admin/ops/evidence-vault/{'{evidence_id}'}/export</code>
          </p>
        </div>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
