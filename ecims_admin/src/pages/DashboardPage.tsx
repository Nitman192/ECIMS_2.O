import { useCallback, useEffect, useMemo, useState } from 'react';
import { FiActivity, FiAlertCircle, FiPower, FiRefreshCw, FiShield } from 'react-icons/fi';
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CoreApi } from '../api/services';
import { getApiErrorMessage, normalizeListResponse } from '../api/utils';
import { ChartCard } from '../components/ChartCard';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';
import { useAuth } from '../store/AuthContext';
import type { AdminMetricsResponse, Agent, Alert, DeviceRolloutStatusResponse, FleetDriftResponse } from '../types';

type DashboardStatus = 'loading' | 'ready' | 'error';

type RecentIncidentRow = {
  id: string;
  asset: string;
  severity: 'High' | 'Medium' | 'Low';
  status: string;
  time: string;
};

const PIE_COLORS = ['#0891b2', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#7c3aed'];

const toTitleCase = (value: string) =>
  value
    .replace(/[_-]+/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());

const formatRelativeTime = (iso: string): string => {
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) return '-';

  const diffSeconds = Math.round((timestamp - Date.now()) / 1000);
  const absSeconds = Math.abs(diffSeconds);

  if (absSeconds < 60) return `${absSeconds}s ago`;
  if (absSeconds < 3600) return `${Math.round(absSeconds / 60)}m ago`;
  if (absSeconds < 86400) return `${Math.round(absSeconds / 3600)}h ago`;
  return `${Math.round(absSeconds / 86400)}d ago`;
};

const normalizeSeverity = (severity: string): 'High' | 'Medium' | 'Low' => {
  const value = severity.toUpperCase();
  if (value === 'RED' || value === 'HIGH' || value === 'CRITICAL') return 'High';
  if (value === 'YELLOW' || value === 'AMBER' || value === 'MEDIUM') return 'Medium';
  return 'Low';
};

const buildEventBuckets = (alerts: Alert[]) => {
  const buckets = Array.from({ length: 12 }, (_, index) => ({
    hour: String(index * 2).padStart(2, '0'),
    events: 0,
  }));

  alerts.forEach((alert) => {
    const timestamp = Date.parse(alert.ts);
    if (Number.isNaN(timestamp)) return;
    const hour = new Date(timestamp).getHours();
    const bucketIndex = Math.min(Math.floor(hour / 2), buckets.length - 1);
    buckets[bucketIndex].events += 1;
  });

  return buckets;
};

const buildPolicyDistribution = (
  rollout: DeviceRolloutStatusResponse | null,
  metrics: AdminMetricsResponse | null,
) => {
  const source = rollout?.rollout ?? metrics?.rollout ?? {};
  return Object.entries(source)
    .map(([name, value]) => ({
      name: toTitleCase(name),
      value: Number(value) || 0,
    }))
    .filter((item) => item.value > 0)
    .sort((left, right) => right.value - left.value);
};

const buildRecentIncidents = (alerts: Alert[], agents: Agent[]): RecentIncidentRow[] => {
  const agentMap = new Map<number, string>();
  agents.forEach((agent) => {
    agentMap.set(agent.id, agent.hostname || agent.name || `AGENT-${agent.id}`);
  });

  const sortedAlerts = [...alerts].sort((left, right) => {
    const leftTime = Date.parse(left.ts);
    const rightTime = Date.parse(right.ts);
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) return 0;
    return rightTime - leftTime;
  });

  return sortedAlerts.slice(0, 6).map((alert) => ({
    id: `INC-${alert.id}`,
    asset: alert.agent_id ? agentMap.get(alert.agent_id) ?? `AGENT-${alert.agent_id}` : 'Unknown',
    severity: normalizeSeverity(alert.severity),
    status: toTitleCase(alert.status || 'Unknown'),
    time: formatRelativeTime(alert.ts),
  }));
};

const resolveDominantMode = (distribution: Array<{ name: string; value: number }>) => {
  if (distribution.length === 0) return 'Unavailable';
  return distribution[0].name;
};

export const DashboardPage = () => {
  const { user } = useAuth();
  const [status, setStatus] = useState<DashboardStatus>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);
  const [rollout, setRollout] = useState<DeviceRolloutStatusResponse | null>(null);
  const [driftCount, setDriftCount] = useState(0);
  const isAdmin = user?.role === 'ADMIN';

  const loadDashboard = useCallback(async () => {
    setStatus('loading');
    setErrorMessage('');

    try {
      const [alertsResult, agentsResult, metricsResult, rolloutResult, driftResult] = await Promise.allSettled([
        CoreApi.alerts(),
        CoreApi.agents(),
        isAdmin ? CoreApi.metrics() : Promise.resolve(null),
        isAdmin ? CoreApi.deviceRolloutStatus() : Promise.resolve(null),
        isAdmin ? CoreApi.fleetDrift() : Promise.resolve(null),
      ]);

      if (alertsResult.status !== 'fulfilled') throw alertsResult.reason;
      if (agentsResult.status !== 'fulfilled') throw agentsResult.reason;

      setAlerts(normalizeListResponse<Alert>(alertsResult.value.data));
      setAgents(normalizeListResponse<Agent>(agentsResult.value.data));

      if (metricsResult.status === 'fulfilled' && metricsResult.value) {
        setMetrics(metricsResult.value.data);
      } else {
        setMetrics(null);
      }

      if (rolloutResult.status === 'fulfilled' && rolloutResult.value) {
        setRollout(rolloutResult.value.data);
      } else {
        setRollout(null);
      }

      if (driftResult.status === 'fulfilled' && driftResult.value) {
        setDriftCount((driftResult.value.data as FleetDriftResponse | null)?.count ?? 0);
      } else {
        setDriftCount(0);
      }

      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load dashboard'));
      setStatus('error');
    }
  }, [isAdmin]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const policyDistribution = useMemo(() => buildPolicyDistribution(rollout, metrics), [rollout, metrics]);
  const eventsByHour = useMemo(() => buildEventBuckets(alerts), [alerts]);
  const recentIncidents = useMemo(() => buildRecentIncidents(alerts, agents), [alerts, agents]);

  const stats = useMemo(() => {
    const onlineAgents = agents.filter((agent) => {
      const statusValue = agent.status?.toUpperCase() ?? '';
      return statusValue === 'ONLINE' && !agent.agent_revoked;
    }).length;

    const openAlerts = alerts.filter((alert) => {
      const statusValue = alert.status?.toUpperCase() ?? '';
      return !['RESOLVED', 'CLOSED'].includes(statusValue);
    }).length;

    const totalAgents = agents.length;
    const onlineRate = totalAgents > 0 ? Math.round((onlineAgents / totalAgents) * 100) : 0;
    const highSeverityAlerts = alerts.filter((alert) => normalizeSeverity(alert.severity) === 'High').length;

    const killSwitchEnabled = rollout?.kill_switch ?? metrics?.kill_switch_state ?? false;
    const dominantMode = resolveDominantMode(policyDistribution);

    return [
      {
        label: 'Active Agents',
        value: onlineAgents.toLocaleString(),
        trendLabel: `${onlineRate}% online across fleet`,
        trend: onlineRate >= 70 ? 'up' : 'neutral',
        icon: FiActivity,
      },
      {
        label: 'Open Alerts',
        value: openAlerts.toLocaleString(),
        trendLabel: `${highSeverityAlerts} high-severity incidents`,
        trend: highSeverityAlerts > 0 ? 'down' : 'up',
        icon: FiAlertCircle,
      },
      {
        label: 'Kill Switch',
        value: killSwitchEnabled ? 'Armed' : 'Disarmed',
        trendLabel: killSwitchEnabled ? 'Immediate containment available' : 'Emergency stop disabled',
        trend: killSwitchEnabled ? 'up' : 'neutral',
        icon: FiPower,
      },
      {
        label: 'Enforcement',
        value: dominantMode,
        trendLabel: `${driftCount} endpoints in drift state`,
        trend: driftCount === 0 ? 'up' : 'down',
        icon: FiShield,
      },
    ] as const;
  }, [agents, alerts, rollout, metrics, policyDistribution, driftCount]);

  return (
    <div className="space-y-8">
      <PageHeader
        title="ECIMS 2.0 Security Operations Dashboard"
        subtitle="Monitor endpoint posture, alert flow, and policy distribution in real time across network."
        action={
          <button type="button" className="btn-secondary" onClick={() => void loadDashboard()}>
            <FiRefreshCw className="mr-2 text-sm" />
            Refresh
          </button>
        }
      />

      {status === 'loading' && (
        <LoadingState
          title="Loading dashboard"
          description="Fetching metrics, rollout posture, alerts, and fleet status from backend APIs."
        />
      )}

      {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadDashboard()} />}

      {status === 'ready' && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((item) => (
              <StatCard
                key={item.label}
                label={item.label}
                value={item.value}
                trendLabel={item.trendLabel}
                trend={item.trend}
                icon={item.icon}
              />
            ))}
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Events Per Hour"
              subtitle="Alert volumes grouped into 2-hour windows from live backend feed"
            >
              {eventsByHour.some((entry) => entry.events > 0) ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={eventsByHour}>
                    <CartesianGrid strokeDasharray="4 4" stroke="#64748b33" />
                    <XAxis
                      dataKey="hour"
                      tick={{ fill: '#94a3b8', fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="events"
                      stroke="#0891b2"
                      strokeWidth={3}
                      dot={{ fill: '#0891b2', r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState
                  title="No event activity"
                  description="No alert telemetry available yet for current environment."
                />
              )}
            </ChartCard>

            <ChartCard
              title="Policy Distribution"
              subtitle="Current rollout mode split across enrolled machines"
            >
              {policyDistribution.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={policyDistribution}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={72}
                      outerRadius={102}
                      paddingAngle={2}
                    >
                      {policyDistribution.map((entry, index) => (
                        <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend verticalAlign="bottom" iconType="circle" />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState
                  title="No rollout data"
                  description="Rollout distribution becomes visible once fleet policy counters are available."
                />
              )}
            </ChartCard>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Recent Incidents</h2>
            {recentIncidents.length > 0 ? (
              <DataTable
                columns={[
                  { key: 'id', header: 'Incident ID' },
                  { key: 'asset', header: 'Asset' },
                  {
                    key: 'severity',
                    header: 'Severity',
                    render: (row: RecentIncidentRow) => {
                      const tone =
                        row.severity === 'High'
                          ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                          : row.severity === 'Medium'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                            : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
                      return (
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
                          {row.severity}
                        </span>
                      );
                    },
                  },
                  { key: 'status', header: 'Status' },
                  { key: 'time', header: 'Updated' },
                ]}
                rows={recentIncidents}
                rowKey={(row) => row.id}
              />
            ) : (
              <EmptyState
                title="No incidents yet"
                description="Incidents will appear here after alerts start flowing from connected endpoints."
              />
            )}
          </section>
        </>
      )}
    </div>
  );
};
